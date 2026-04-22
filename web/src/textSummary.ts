import type { ComparisonItem } from './api';

export type ExcerptBucket = 'advice' | 'grading' | 'abnormal' | 'other';

export interface ExcerptSentence {
  text: string;
  bucket: ExcerptBucket;
  isNew: boolean;
}

export interface SubSection {
  label: string;
  content: string;
}

export interface ParsedSection {
  key: string;
  label: string;
  rawText: string;
  subSections: SubSection[];
  abnormalSentences: ExcerptSentence[];
  gradingSentences: ExcerptSentence[];
  adviceSentences: ExcerptSentence[];
  otherSentences: ExcerptSentence[];
  hasExcerpt: boolean;
}

export interface ParsedComparisonText {
  code: string;
  name: string;
  category: string;
  latestDate: string;
  latestText: string;
  previousText: string | null;
  hasPrevious: boolean;
  sections: ParsedSection[];
}

export interface TextSummaryOverview {
  itemCount: number;
  sectionCount: number;
  excerptSectionCount: number;
  abnormalCount: number;
  gradingCount: number;
  adviceCount: number;
  withPreviousCount: number;
}

const ADVICE_RE = /建议|复查|随访|进一步|动态观察|结合临床|必要时|建议完善|定期复查|请结合/;
const GRADING_RE = /TI-RADS|BI-RADS|PIRADS|RADS|[0-9一二三四五六七八九十]+级|分级|分层/;
const STABLE_RE = /未见明显异常|未见异常|无明显异常|正常|较前无明显变化|未见明显变化|未闻及异常呼吸音|无叩痛|未闻及|位置正常|大小正常|形态正常|符合.*表现/;
const ABNORMAL_RE = /结节|占位|病变|增厚|阳性|息肉|囊肿|斑块|肿大|积液|钙化|结石|炎症|狭窄|返流|反流|功能改变|肌瘤|低回声|高回声|欠均匀|硬化|异常回声|慢性咽炎|脂肪肝|囊性|囊实性|骨密度减低|骨质疏松|甲减|粥样硬化/;
const HEADER_L1_RE = /(?:^|\n)\s*(?:[一二三四五六七八九十]{1,3}[.、．]\s*[^\n]{2,40}[:：]?|【\d+[.、].+?】)/gm;
const HEADER_L2_RE = /(?:^|\n)\s*(?:H-[^\n:：]{2,40}[:：]?|(?:\d+)[.、]\s*[^\n]{2,40}[:：]?)/gm;
const HEADER_RE = /(?:^|\n)\s*(?:[一二三四五六七八九十]{1,3}[.、．]\s*[^\n]{2,40}[:：]?|H-[^\n:：]{2,40}[:：]?|【\d+[.、].+?】|(?:\d+)[.、]\s*[^\n]{2,40}[:：]?)/gm;

export function cleanTextBlock(raw: string): string {
  return raw
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/\t/g, ' ')
    .replace(/[ ]{2,}/g, ' ')
    .split('\n')
    .map(line => line.trim())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export function splitSentences(text: string): string[] {
  return cleanTextBlock(text)
    .split(/\n+|(?<=[。！？；])\s*/)
    .map(part => part.trim())
    .filter(Boolean);
}

function normalizeSentence(text: string): string {
  return text.replace(/\s+/g, '').replace(/[，,。！？；;：:、]/g, '');
}

function normalizeLabel(text: string): string {
  return text.replace(/\s+/g, '').replace(/[：:]/g, '');
}

/** Split content by L2 headers (H-xxx:) into sub-sections. */
function splitSubSections(content: string): SubSection[] {
  const cleaned = cleanTextBlock(content);
  HEADER_L2_RE.lastIndex = 0;
  const headers: Array<{ index: number; label: string; full: string }> = [];
  let match: RegExpExecArray | null;

  while ((match = HEADER_L2_RE.exec(cleaned)) !== null) {
    const full = match[0].replace(/^\s+/, '');
    const label = full.replace(/[:：\s]+$/, '').trim();
    headers.push({ index: match.index, label, full });
  }

  if (headers.length === 0) {
    return []; // No sub-sections
  }

  const subs: SubSection[] = [];
  // Preamble before first sub-header
  if (headers[0].index > 0) {
    const pre = cleaned.slice(0, headers[0].index).trim();
    if (pre) subs.push({ label: '概述', content: pre });
  }

  for (let i = 0; i < headers.length; i++) {
    const start = headers[i].index + headers[i].full.length;
    const end = i + 1 < headers.length ? headers[i + 1].index : cleaned.length;
    const sub = cleaned.slice(start, end).trim();
    if (sub) subs.push({ label: headers[i].label, content: sub });
  }

  return subs;
}

export function splitBySections(text: string): Array<{ label: string; content: string; subSections: SubSection[] }> {
  const cleaned = cleanTextBlock(text);
  HEADER_L1_RE.lastIndex = 0;
  const headers: Array<{ index: number; label: string; full: string }> = [];
  let match: RegExpExecArray | null;

  // First try L1 headers (一. ~ 二十一.)
  while ((match = HEADER_L1_RE.exec(cleaned)) !== null) {
    const full = match[0].replace(/^\s+/, '');
    const label = full.replace(/[:：\s]+$/, '').trim();
    headers.push({ index: match.index, label, full });
  }

  // If no L1 headers, fall back to combined regex
  if (headers.length === 0) {
    HEADER_RE.lastIndex = 0;
    while ((match = HEADER_RE.exec(cleaned)) !== null) {
      const full = match[0].replace(/^\s+/, '');
      const label = full.replace(/[:：\s]+$/, '').trim();
      headers.push({ index: match.index, label, full });
    }
  }

  if (headers.length === 0) {
    const paragraphs = cleaned.split(/\n\n+/).map(part => part.trim()).filter(Boolean);
    if (paragraphs.length <= 1) {
      return [{ label: '未归类内容', content: cleaned, subSections: [] }];
    }
    return paragraphs.map((content, index) => ({ label: `段落 ${index + 1}`, content, subSections: [] }));
  }

  const sections: Array<{ label: string; content: string; subSections: SubSection[] }> = [];
  if (headers[0].index > 0) {
    const preamble = cleaned.slice(0, headers[0].index).trim();
    if (preamble) {
      sections.push({ label: '概述', content: preamble, subSections: [] });
    }
  }

  for (let index = 0; index < headers.length; index += 1) {
    const current = headers[index];
    const start = current.index + current.full.length;
    const end = index + 1 < headers.length ? headers[index + 1].index : cleaned.length;
    const content = cleaned.slice(start, end).trim();
    if (content) {
      const subSections = splitSubSections(content);
      sections.push({ label: current.label, content, subSections });
    }
  }

  return sections.length > 0 ? sections : [{ label: '未归类内容', content: cleaned, subSections: [] }];
}

export function classifySentenceBucket(sentence: string): ExcerptBucket {
  if (ADVICE_RE.test(sentence)) return 'advice';
  if (GRADING_RE.test(sentence)) return 'grading';

  const hasStrongAbnormal = ABNORMAL_RE.test(sentence) || (/异常/.test(sentence) && !/未见明显异常|无明显异常|未闻及异常/.test(sentence));
  const hasStableOnly = STABLE_RE.test(sentence) && !hasStrongAbnormal;

  if (hasStableOnly) return 'other';
  if (hasStrongAbnormal) return 'abnormal';
  return 'other';
}

export function pickNearestPrevious(record: ComparisonItem, examDates: string[], currentDate: string): string | null {
  const currentIndex = examDates.indexOf(currentDate);
  for (let index = currentIndex - 1; index >= 0; index -= 1) {
    const candidate = record.values[examDates[index]];
    if (candidate != null && String(candidate).trim() !== '') {
      return String(candidate);
    }
  }
  return null;
}

function buildPreviousSectionMap(previousText: string | null): Map<string, string> {
  const map = new Map<string, string>();
  if (!previousText) return map;
  for (const section of splitBySections(previousText)) {
    map.set(normalizeLabel(section.label), section.content);
  }
  return map;
}

function isSentenceNew(sentence: string, previousSectionText: string | null): boolean {
  if (!previousSectionText) return false;
  const previousSet = new Set(splitSentences(previousSectionText).map(normalizeSentence));
  return !previousSet.has(normalizeSentence(sentence));
}

function toExcerptSentence(sentence: string, previousText: string | null, bucket: ExcerptBucket): ExcerptSentence {
  return {
    text: sentence,
    bucket,
    isNew: isSentenceNew(sentence, previousText),
  };
}

export function buildParsedComparisonText(record: ComparisonItem, examDates: string[]): ParsedComparisonText | null {
  if (examDates.length === 0) return null;
  const latestDate = examDates[examDates.length - 1];
  const latestRaw = record.values[latestDate];
  if (latestRaw == null || String(latestRaw).trim() === '') return null;

  const latestText = cleanTextBlock(String(latestRaw));
  const previousText = pickNearestPrevious(record, examDates, latestDate);
  const previousSectionMap = buildPreviousSectionMap(previousText);

  const sections = splitBySections(latestText).map((section, index): ParsedSection => {
    const labelKey = normalizeLabel(section.label);
    const previousSectionText = previousSectionMap.get(labelKey) ?? previousText;
    const abnormalSentences: ExcerptSentence[] = [];
    const gradingSentences: ExcerptSentence[] = [];
    const adviceSentences: ExcerptSentence[] = [];
    const otherSentences: ExcerptSentence[] = [];

    for (const sentence of splitSentences(section.content)) {
      const bucket = classifySentenceBucket(sentence);
      const excerpt = toExcerptSentence(sentence, previousSectionText, bucket);
      if (bucket === 'advice') adviceSentences.push(excerpt);
      else if (bucket === 'grading') gradingSentences.push(excerpt);
      else if (bucket === 'abnormal') abnormalSentences.push(excerpt);
      else otherSentences.push(excerpt);
    }

    return {
      key: `${record.standard_code}-${index}`,
      label: section.label,
      rawText: cleanTextBlock(section.content),
      subSections: section.subSections || [],
      abnormalSentences,
      gradingSentences,
      adviceSentences,
      otherSentences,
      hasExcerpt: abnormalSentences.length > 0 || gradingSentences.length > 0 || adviceSentences.length > 0,
    };
  });

  return {
    code: record.standard_code,
    name: record.standard_name,
    category: record.category,
    latestDate,
    latestText,
    previousText,
    hasPrevious: Boolean(previousText),
    sections,
  };
}

export function buildTextSummaryOverview(items: ParsedComparisonText[]): TextSummaryOverview {
  return items.reduce<TextSummaryOverview>((acc, item) => {
    acc.itemCount += 1;
    acc.sectionCount += item.sections.length;
    acc.excerptSectionCount += item.sections.filter(section => section.hasExcerpt).length;
    acc.abnormalCount += item.sections.reduce((sum, section) => sum + section.abnormalSentences.length, 0);
    acc.gradingCount += item.sections.reduce((sum, section) => sum + section.gradingSentences.length, 0);
    acc.adviceCount += item.sections.reduce((sum, section) => sum + section.adviceSentences.length, 0);
    acc.withPreviousCount += item.hasPrevious ? 1 : 0;
    return acc;
  }, {
    itemCount: 0,
    sectionCount: 0,
    excerptSectionCount: 0,
    abnormalCount: 0,
    gradingCount: 0,
    adviceCount: 0,
    withPreviousCount: 0,
  });
}
