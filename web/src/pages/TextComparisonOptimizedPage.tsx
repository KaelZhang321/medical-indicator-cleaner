import { useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Collapse, Input, List, Row, Select, Space, Statistic, Switch, Table, Tag, Typography, message } from 'antd';
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

function pickNearestPrevious(record: ComparisonItem, examDates: string[], currentDate: string): string | null {
  const currentIndex = examDates.indexOf(currentDate);
  for (let index = currentIndex - 1; index >= 0; index -= 1) {
    const candidate = record.values[examDates[index]];
    if (candidate != null && String(candidate).trim() !== '') {
      return String(candidate);
    }
  }
  return null;
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

function scoreSentence(sentence: string): number {
  let score = 0;
  if (/结节|占位|病变|增厚|异常|阳性|息肉|囊肿|斑块/.test(sentence)) score += 3;
  if (/建议|复查|随访|进一步|结合临床|动态观察/.test(sentence)) score += 2;
  if (/TI-RADS|BI-RADS|级|分级/.test(sentence)) score += 2;
  if (/\d+(\.\d+)?\s*(cm|mm)/i.test(sentence)) score += 2;
  return score;
}

function sentenceBadgeColor(sentence: string): string {
  if (/建议|复查|随访|进一步|动态观察/.test(sentence)) return 'red';
  if (/结节|占位|病变|增厚|异常|阳性|息肉|囊肿|斑块/.test(sentence)) return 'orange';
  if (/TI-RADS|BI-RADS|级|分级/.test(sentence)) return 'gold';
  return 'blue';
}

type ChangeKind = 'recommendation' | 'lesion' | 'grading' | 'other';

const CHANGE_KIND_LABEL: Record<ChangeKind, string> = {
  recommendation: '建议/随访',
  lesion: '病灶/结构变化',
  grading: '分级/等级变化',
  other: '其他变化',
};

const CHANGE_KIND_COLOR: Record<ChangeKind, string> = {
  recommendation: 'red',
  lesion: 'orange',
  grading: 'gold',
  other: 'blue',
};

function classifySentenceKind(sentence: string): ChangeKind {
  if (/建议|复查|随访|进一步|动态观察|结合临床|必要时/.test(sentence)) return 'recommendation';
  if (/TI-RADS|BI-RADS|PIRADS|RADS|级|分级|分层/.test(sentence)) return 'grading';
  if (/结节|占位|病变|增厚|异常|阳性|息肉|囊肿|斑块|肿大|积液|钙化|结石|炎症|回声/.test(sentence)) return 'lesion';
  return 'other';
}

interface ChangeSummary {
  code: string;
  name: string;
  category: string;
  latestDate: string;
  latestText: string;
  previousText: string | null;
  added: string[];
  removed: string[];
  score: number;
  kind: ChangeKind;
}

function buildChangeSummaries(data: ComparisonResponse | null): ChangeSummary[] {
  if (!data || data.exam_dates.length === 0) return [];
  const latestDate = data.exam_dates[data.exam_dates.length - 1];

  return data.comparisons.map(record => {
    const latestRaw = record.values[latestDate];
    const latestText = latestRaw == null ? '' : String(latestRaw);
    const previousText = pickNearestPrevious(record, data.exam_dates, latestDate);
    const added = diffSentences(latestText, previousText);
    const removed = removedSentences(latestText, previousText);
    const score = [...added, ...removed].reduce((sum, sentence) => sum + scoreSentence(sentence), 0);
    const kindSource = [...added, ...removed][0] || latestText || record.standard_name;
    const kind = classifySentenceKind(kindSource);

    return {
      code: record.standard_code,
      name: record.standard_name,
      category: record.category,
      latestDate,
      latestText,
      previousText,
      added,
      removed,
      score,
      kind,
    };
  }).sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return (b.added.length + b.removed.length) - (a.added.length + a.removed.length);
  });
}

function DetailCell({ current, previous }: { current?: string | number | null; previous?: string | null }) {
  const text = current == null ? '-' : String(current);
  const added = text === '-' ? [] : diffSentences(text, previous);

  return (
    <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
      <Typography.Text>{text}</Typography.Text>
      {added.length > 0 && (
        <div style={{ marginTop: 6 }}>
          {added.slice(0, 3).map((sentence, index) => (
            <Tag key={`${sentence}-${index}`} color="orange" style={{ marginBottom: 4 }}>
              {sentence}
            </Tag>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TextComparisonOptimizedPage() {
  const [sfzh, setSfzh] = useState('');
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailOnlyChanged, setDetailOnlyChanged] = useState(true);

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
  const summaries = useMemo(() => buildChangeSummaries(data), [data]);
  const changedSummaries = summaries.filter(item => item.added.length > 0 || item.removed.length > 0);
  const groupedSummaries = useMemo(() => {
    const result: Record<ChangeKind, ChangeSummary[]> = {
      recommendation: [],
      lesion: [],
      grading: [],
      other: [],
    };
    for (const item of changedSummaries) {
      result[item.kind].push(item);
    }
    return result;
  }, [changedSummaries]);
  const stableCount = summaries.length - changedSummaries.length;
  const recommendationCount = groupedSummaries.recommendation.length;
  const detailVisibleData = useMemo(
    () => detailOnlyChanged ? data?.comparisons.filter(record => changedSummaries.some(item => item.code === record.standard_code)) || [] : (data?.comparisons || []),
    [changedSummaries, data, detailOnlyChanged],
  );
  const latestDate = data?.exam_dates[data.exam_dates.length - 1];
  const detailColumns: ColumnsType<ComparisonItem> = [
    { title: '项目', dataIndex: 'standard_name', width: 180, fixed: 'left' },
    { title: '分类', dataIndex: 'category', width: 120, render: (c: string) => <Tag color="blue">{c}</Tag> },
    ...([...(data?.exam_dates || [])].reverse()).map(date => ({
      title: date,
      key: date,
      width: 260,
      render: (_: any, record: ComparisonItem) => {
        const value = record.values[date];
        const previous = latestDate && date === latestDate ? pickNearestPrevious(record, data?.exam_dates || [], date) : null;
        return <DetailCell current={value} previous={previous} />;
      },
    })),
  ];

  return (
    <div className="page-shell">
      <div className="page-head">
        <div>
          <div className="page-kicker">Clinician Reading View</div>
          <h1 className="page-title">影像/结论优化版</h1>
          <div className="page-subtitle">面向医生阅读的摘要化视图，先给重点变化，再按需展开时间轴明细。</div>
        </div>
        <div className="page-status-chip">摘要优先的医生解读模式</div>
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
        </div>
      </Card>

      {data && (
        <>
          <Alert
            showIcon
            type={changedSummaries.length > 0 ? 'warning' : 'success'}
            message={changedSummaries.length > 0 ? '已按最近一次有结果的检查提炼重点变化' : '最近一次与既往文本结果相比未见明确重点变化'}
            description={changedSummaries.length > 0 ? `建议先阅读下方“重点变化摘要”，再查看时间轴明细。当前共识别 ${changedSummaries.length} 项变化，涉及建议/随访 ${recommendationCount} 项。` : '当前更适合直接查看时间轴明细确认稳定项。'}
            style={{ marginBottom: 16 }}
          />

          <Row gutter={16} className="stat-grid" style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card className="stat-card"><Statistic title="文本项目" value={summaries.length} /></Card>
            </Col>
            <Col span={6}>
              <Card className="stat-card"><Statistic title="重点变化" value={changedSummaries.length} valueStyle={{ color: changedSummaries.length > 0 ? '#d46b08' : '#389e0d' }} /></Card>
            </Col>
            <Col span={6}>
              <Card className="stat-card"><Statistic title="建议/随访" value={recommendationCount} valueStyle={{ color: recommendationCount > 0 ? '#cf1322' : undefined }} /></Card>
            </Col>
            <Col span={6}>
              <Card className="stat-card"><Statistic title="稳定项目" value={stableCount} /></Card>
            </Col>
          </Row>

          <Card
            className="section-card"
            title="重点变化摘要"
            style={{ marginBottom: 16 }}
            extra={<Typography.Text type="secondary">先看建议/随访，再看病灶和分级变化</Typography.Text>}
          >
            <Collapse
              defaultActiveKey={['recommendation', 'lesion', 'grading']}
              items={(['recommendation', 'lesion', 'grading', 'other'] as ChangeKind[]).map(kind => ({
                key: kind,
                label: `${CHANGE_KIND_LABEL[kind]} (${groupedSummaries[kind].length})`,
                children: groupedSummaries[kind].length > 0 ? (
                  <List
                    dataSource={groupedSummaries[kind].slice(0, 6)}
                    locale={{ emptyText: '暂无' }}
                    renderItem={item => (
                      <List.Item style={{ paddingLeft: 0, paddingRight: 0 }}>
                        <Card size="small" style={{ width: '100%' }}>
                          <Space wrap style={{ marginBottom: 8 }}>
                            <Typography.Text strong>{item.name}</Typography.Text>
                            <Tag color={CHANGE_KIND_COLOR[item.kind]}>{CHANGE_KIND_LABEL[item.kind]}</Tag>
                            <Tag color="orange">重点分 {item.score}</Tag>
                            <Tag>{item.latestDate}</Tag>
                          </Space>
                          {item.added.length > 0 && (
                            <div style={{ marginBottom: item.removed.length > 0 ? 10 : 0 }}>
                              {item.added.slice(0, 4).map((sentence, index) => (
                                <div key={`${item.code}-add-${index}`} style={{ marginBottom: 6 }}>
                                  <Tag color={sentenceBadgeColor(sentence)} style={{ marginRight: 8 }}>
                                    新增
                                  </Tag>
                                  <Typography.Text>{sentence}</Typography.Text>
                                </div>
                              ))}
                            </div>
                          )}
                          {item.removed.length > 0 && (
                            <div>
                              {item.removed.slice(0, 3).map((sentence, index) => (
                                <div key={`${item.code}-remove-${index}`} style={{ marginBottom: 6 }}>
                                  <Tag color="red" style={{ marginRight: 8 }}>
                                    消失
                                  </Tag>
                                  <Typography.Text type="secondary">{sentence}</Typography.Text>
                                </div>
                              ))}
                            </div>
                          )}
                        </Card>
                      </List.Item>
                    )}
                  />
                ) : (
                  <Alert type="success" showIcon message="暂无重点变化" />
                ),
              }))}
            />
          </Card>

          <Card
            className="section-card table-card"
            title="时间轴明细"
            style={{ marginBottom: 16 }}
            extra={(
              <Space wrap>
                <Switch
                  checkedChildren="仅看变化"
                  unCheckedChildren="全部项目"
                  checked={detailOnlyChanged}
                  onChange={setDetailOnlyChanged}
                  disabled={!detailOpen}
                />
                <Button type="primary" onClick={() => setDetailOpen(v => !v)}>
                  {detailOpen ? '收起明细' : '展开明细'}
                </Button>
              </Space>
            )}
          >
            {!detailOpen ? (
              <Alert
                type="info"
                showIcon
                message="明细已收起"
                description="摘要区已经优先显示重点变化。需要核对原始时间轴时，再展开明细。"
              />
            ) : (
              <Table
                columns={detailColumns}
                dataSource={detailVisibleData}
                rowKey="standard_code"
                size="small"
                pagination={{ pageSize: 10 }}
                scroll={{ x: 1100 }}
              />
            )}
          </Card>
        </>
      )}
    </div>
  );
}
