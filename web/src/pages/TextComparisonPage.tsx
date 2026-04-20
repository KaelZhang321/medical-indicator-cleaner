import { useMemo, useState } from 'react';
import { Input, Button, Table, Tag, Select, Switch, message, Typography, Card } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { fetchTextComparison, type ComparisonItem, type ComparisonResponse } from '../api';

function splitSentences(text: string): string[] {
  return text
    .split(/\n+|(?<=[。！？；])\s*/)
    .map(part => part.trim())
    .filter(Boolean);
}

function normalizeSentence(text: string): string {
  return text.replace(/\s+/g, '').replace(/[，,。！？；;：:、]/g, '');
}

function diffSentences(current: string, previous?: string | null): string[] {
  const currentSentences = splitSentences(current);
  if (!previous) return currentSentences;
  const previousSet = new Set(splitSentences(previous).map(normalizeSentence));
  return currentSentences.filter(sentence => !previousSet.has(normalizeSentence(sentence)));
}

function removedSentences(current: string, previous?: string | null): string[] {
  if (!previous) return [];
  const currentSet = new Set(splitSentences(current).map(normalizeSentence));
  return splitSentences(previous).filter(sentence => !currentSet.has(normalizeSentence(sentence)));
}

function pickNearestPreviousValue(
  record: ComparisonItem,
  examDates: string[],
  currentDate: string,
): string | number | null {
  const currentIndex = examDates.indexOf(currentDate);
  for (let index = currentIndex - 1; index >= 0; index -= 1) {
    const candidate = record.values[examDates[index]];
    if (candidate != null && String(candidate).trim() !== '') {
      return candidate;
    }
  }
  return null;
}

function TextCell({ current, previous }: { current?: string | number | null; previous?: string | number | null }) {
  const [expanded, setExpanded] = useState(false);
  const text = current == null ? '-' : String(current);
  const previousText = previous == null ? '' : String(previous);
  const sentences = useMemo(() => splitSentences(text), [text]);
  const added = useMemo(() => diffSentences(text, previousText), [text, previousText]);
  const removed = useMemo(() => removedSentences(text, previousText), [text, previousText]);
  const shouldCollapse = sentences.length > 2 || text.length > 48;
  const previewSentences = sentences.slice(0, 2);
  const previewText = previewSentences.join(' / ');

  if (text === '-') {
    return <span>-</span>;
  }

  return (
    <div style={{ lineHeight: 1.6, minWidth: 160, maxWidth: 240, overflow: 'hidden' }}>
      <Typography.Text style={{ display: 'block', whiteSpace: expanded ? 'pre-wrap' : 'normal', wordBreak: 'break-word' }}>
        {shouldCollapse && !expanded ? previewText : text}
      </Typography.Text>
      {(added.length > 0 || (removed.length > 0 && expanded)) && (
        <div style={{ marginTop: 6, display: 'grid', gap: 4 }}>
          {added.slice(0, expanded ? 4 : 1).map((sentence, index) => (
            <div key={`add-${sentence}-${index}`} style={{ minWidth: 0 }}>
              <Tag color="orange" style={{ maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block', margin: 0 }}>
                新增: {sentence}
              </Tag>
            </div>
          ))}
          {removed.slice(0, expanded ? 3 : 0).map((sentence, index) => (
            <div key={`remove-${sentence}-${index}`} style={{ minWidth: 0 }}>
              <Tag color="red" style={{ maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block', margin: 0 }}>
                消失: {sentence}
              </Tag>
            </div>
          ))}
        </div>
      )}
      {shouldCollapse && (
        <Button type="link" size="small" style={{ padding: 0, marginTop: 4 }} onClick={() => setExpanded(v => !v)}>
          {expanded ? '收起' : '展开'}
        </Button>
      )}
    </div>
  );
}

export default function TextComparisonPage() {
  const [sfzh, setSfzh] = useState('');
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [onlyChanged, setOnlyChanged] = useState(false);

  const handleSearch = async () => {
    if (!sfzh.trim()) {
      message.warning('请输入身份证号');
      return;
    }
    setLoading(true);
    try {
      const result = await fetchTextComparison(sfzh.trim(), category);
      setData(result);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '查询失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const categories = data ? [...new Set(data.comparisons.map(c => c.category).filter(Boolean))] : [];
  const filteredComparisons = useMemo(
    () => onlyChanged ? (data?.comparisons.filter(item => item.trend === '变化') || []) : (data?.comparisons || []),
    [data, onlyChanged],
  );
  const changedCount = data?.comparisons.filter(item => item.trend === '变化').length || 0;

  const columns: ColumnsType<ComparisonItem> = [
    { title: '项目', dataIndex: 'standard_name', width: 180 },
    { title: '分类', dataIndex: 'category', width: 120, render: (c: string) => <Tag color="blue">{c}</Tag> },
    ...([...(data?.exam_dates || [])].reverse()).map(date => ({
      title: date,
      key: date,
      width: 260,
      render: (_: any, record: ComparisonItem) => {
        const val = record.values[date];
        const previous = pickNearestPreviousValue(record, data?.exam_dates || [], date);
        return <TextCell current={val} previous={previous} />;
      },
    })),
    {
      title: '变化',
      dataIndex: 'trend',
      width: 100,
      render: (t: string) => <Tag color={t === '变化' ? 'orange' : t === '一致' ? 'green' : 'default'}>{t || '-'}</Tag>,
    },
  ];

  return (
    <div className="page-shell">
      <div className="page-head">
        <div>
          <div className="page-kicker">Raw Text Timeline</div>
          <h1 className="page-title">影像/结论对比</h1>
          <div className="page-subtitle">保留原始文本对比阅读方式，用于逐期核对影像结论、所见与建议的具体变化。</div>
        </div>
        <div className="page-status-chip">原始文本时间轴视图</div>
      </div>

      <Card className="query-panel" style={{ marginBottom: 24 }}>
        <div className="query-toolbar">
          <Input
            placeholder="输入身份证号"
            value={sfzh}
            onChange={e => setSfzh(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 260 }}
          />
          <Select
            placeholder="筛选分类"
            allowClear
            style={{ width: 180 }}
            value={category}
            onChange={setCategory}
            options={categories.map(c => ({ label: c, value: c }))}
          />
          <Button type="primary" onClick={handleSearch} loading={loading}>对比查询</Button>
          {data && (
            <Switch
              checkedChildren="仅看变化"
              unCheckedChildren="全部项目"
              checked={onlyChanged}
              onChange={setOnlyChanged}
            />
          )}
        </div>
      </Card>

      {data && (
        <>
          <Card className="summary-card" size="small" style={{ marginBottom: 16 }}>
            共 {data.comparisons.length} 项文本结果，较上次有变化 {changedCount} 项。
          </Card>
          <Card className="section-card table-card">
            <Table
              columns={columns}
              dataSource={filteredComparisons}
              rowKey="standard_code"
              size="small"
              pagination={{ pageSize: 15 }}
              scroll={{ x: 980 }}
            />
          </Card>
        </>
      )}
    </div>
  );
}
