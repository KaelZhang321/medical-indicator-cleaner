import { useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Collapse, Input, Row, Select, Space, Statistic, Switch, Tag, Typography, message } from 'antd';
import { fetchTextComparison, type ComparisonResponse } from '../api';
import { extractErrorMessage } from '../errorUtils';
import {
  buildParsedComparisonText,
  buildTextSummaryOverview,
  type ExcerptSentence,
  type ParsedComparisonText,
  type ParsedSection,
} from '../textSummary';

function renderExcerptList(sentences: ExcerptSentence[], label: string, color: string) {
  if (sentences.length === 0) return null;

  return (
    <div style={{ marginBottom: 10 }}>
      {sentences.map((sentence, index) => (
        <div key={`${label}-${index}`} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6 }}>
          <Tag color={color} style={{ margin: 0, flex: 'none' }}>
            {label}
          </Tag>
          <Typography.Text style={{ lineHeight: 1.8 }}>
            {sentence.text}
            {sentence.isNew && <Tag color="orange" style={{ marginLeft: 8 }}>较前新增</Tag>}
          </Typography.Text>
        </div>
      ))}
    </div>
  );
}


function RawSectionCollapse({ item }: { item: ParsedComparisonText }) {
  return (
    <Collapse
      size="small"
      items={item.sections.map(section => ({
        key: section.key,
        label: (
          <Space wrap>
            <Typography.Text strong>{section.label}</Typography.Text>
            <Tag color={section.hasExcerpt ? 'orange' : 'default'}>
              {section.hasExcerpt ? '含重点摘录' : '仅原文'}
            </Tag>
            {section.subSections.length > 0 && <Tag color="purple">{section.subSections.length}个子项</Tag>}
          </Space>
        ),
        children: section.subSections.length > 0 ? (
          <div>
            {section.subSections.map((sub, si) => (
              <Card key={`${section.key}-sub-${si}`} size="small" style={{ marginBottom: 8 }}
                title={<Typography.Text strong style={{ fontSize: 13 }}>{sub.label}</Typography.Text>}
              >
                {sub.content.split('\n').filter(Boolean).map((line, li) => {
                  const isAbnormal = /结节|占位|病变|增厚|阳性|息肉|囊肿|斑块|肿大|钙化|结石|炎症|反流|肌瘤|异常|硬化/.test(line);
                  const isAdvice = /建议|复查|随访|动态观察|结合临床/.test(line);
                  const isGrading = /TI-RADS|BI-RADS|RADS|级/.test(line);
                  return (
                    <div key={`line-${li}`} style={{ marginBottom: 4, paddingLeft: 4 }}>
                      {isAdvice && <Tag color="red" style={{ marginRight: 6 }}>建议</Tag>}
                      {isGrading && <Tag color="gold" style={{ marginRight: 6 }}>分级</Tag>}
                      {isAbnormal && !isAdvice && !isGrading && <Tag color="orange" style={{ marginRight: 6 }}>异常</Tag>}
                      <Typography.Text style={{ color: isAdvice ? '#cf1322' : isAbnormal ? '#d46b08' : undefined }}>
                        {line}
                      </Typography.Text>
                    </div>
                  );
                })}
              </Card>
            ))}
          </div>
        ) : (
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0, lineHeight: 1.9 }}>
            {section.rawText}
          </Typography.Paragraph>
        ),
      }))}
    />
  );
}

export default function TextComparisonOptimizedPage() {
  const [sfzh, setSfzh] = useState('');
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [detailOnlyExcerptSections, setDetailOnlyExcerptSections] = useState(true);

  const handleSearch = async () => {
    if (!sfzh.trim()) {
      message.warning('请输入身份证号');
      return;
    }
    setLoading(true);
    try {
      const result = await fetchTextComparison(sfzh.trim(), category);
      setData(result);
    } catch (error: unknown) {
      message.error(extractErrorMessage(error, '查询失败'));
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const categories = data ? [...new Set(data.comparisons.map(c => c.category).filter(Boolean))] : [];
  const parsedItems = useMemo(
    () => (data ? data.comparisons.map(item => buildParsedComparisonText(item, data.exam_dates)).filter((item): item is ParsedComparisonText => Boolean(item)) : []),
    [data],
  );
  const overview = useMemo(() => buildTextSummaryOverview(parsedItems), [parsedItems]);

  const excerptBlocks = useMemo(
    () => parsedItems.flatMap(item => item.sections.map(section => ({ item, section }))),
    [parsedItems],
  );
  const visibleExcerptBlocks = detailOnlyExcerptSections
    ? excerptBlocks.filter(block => block.section.hasExcerpt)
    : excerptBlocks;

  return (
    <div className="page-shell">
      <div className="page-head">
        <div>
          <div className="page-kicker">Clinician Reading View</div>
          <h1 className="page-title">影像/结论优化版</h1>
          <div className="page-subtitle">先展示最新一次文本中的重点摘录，再按原文标题/段落展示完整内容，帮助医生先抓重点、再核原文。</div>
        </div>
        <div className="page-status-chip">确定性摘录 + 原文保留</div>
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
            type={overview.excerptSectionCount > 0 ? 'warning' : 'success'}
            message={overview.excerptSectionCount > 0 ? '已从最新一次文本中提炼重点摘录' : '最新一次文本中未识别到重点摘录，建议直接查看原文'}
            description="上层只展示异常、分级变化和明确建议/随访句。其余正常/稳定内容完整保留在下方原文中。"
            style={{ marginBottom: 16 }}
          />

          <Row gutter={16} className="stat-grid" style={{ marginBottom: 16 }}>
            <Col span={4}>
              <Card className="stat-card"><Statistic title="文本项目" value={overview.itemCount} /></Card>
            </Col>
            <Col span={5}>
              <Card className="stat-card"><Statistic title="标题/段落分组" value={overview.sectionCount} /></Card>
            </Col>
            <Col span={5}>
              <Card className="stat-card"><Statistic title="有重点摘录段落" value={overview.excerptSectionCount} valueStyle={{ color: overview.excerptSectionCount > 0 ? '#d46b08' : '#389e0d' }} /></Card>
            </Col>
            <Col span={5}>
              <Card className="stat-card"><Statistic title="分级摘录" value={overview.gradingCount} valueStyle={{ color: '#ad8b00' }} /></Card>
            </Col>
            <Col span={5}>
              <Card className="stat-card"><Statistic title="建议/随访摘录" value={overview.adviceCount} valueStyle={{ color: '#cf1322' }} /></Card>
            </Col>
          </Row>

          {/* 重点摘要：只显示有异常/建议/分级的条目，紧凑展示 */}
          <Card
            className="section-card"
            title={`重点发现 (${visibleExcerptBlocks.filter(b => b.section.hasExcerpt).length} 段)`}
            style={{ marginBottom: 16 }}
            extra={<Typography.Text type="secondary">仅展示异常、分级和建议项</Typography.Text>}
          >
            {visibleExcerptBlocks.filter(b => b.section.hasExcerpt).length === 0 ? (
              <Alert type="success" showIcon message="未识别到重点发现，建议查看下方原文确认" />
            ) : (
              <Collapse
                size="small"
                defaultActiveKey={visibleExcerptBlocks.filter(b => b.section.hasExcerpt).slice(0, 3).map(b => `${b.item.code}-${b.section.key}`)}
                items={visibleExcerptBlocks.filter(b => b.section.hasExcerpt).map(block => ({
                  key: `${block.item.code}-${block.section.key}`,
                  label: (
                    <span>
                      <Tag color="blue">{block.item.name}</Tag>
                      <Typography.Text strong>{block.section.label}</Typography.Text>
                      {block.section.adviceSentences.length > 0 && <Tag color="red" style={{ marginLeft: 6 }}>建议{block.section.adviceSentences.length}</Tag>}
                      {block.section.gradingSentences.length > 0 && <Tag color="gold">分级{block.section.gradingSentences.length}</Tag>}
                      {block.section.abnormalSentences.length > 0 && <Tag color="orange">异常{block.section.abnormalSentences.length}</Tag>}
                    </span>
                  ),
                  children: (
                    <div>
                      {renderExcerptList(block.section.adviceSentences, '建议', 'red')}
                      {renderExcerptList(block.section.gradingSentences, '分级', 'gold')}
                      {renderExcerptList(block.section.abnormalSentences, '异常', 'orange')}
                    </div>
                  ),
                }))}
              />
            )}
          </Card>

          {/* 完整原文：折叠展示，需要时展开 */}
          <Card
            className="section-card"
            title="完整原文"
            style={{ marginBottom: 16 }}
            extra={
              <Switch
                checkedChildren="仅看重点段落"
                unCheckedChildren="全部段落"
                checked={detailOnlyExcerptSections}
                onChange={setDetailOnlyExcerptSections}
              />
            }
          >
            <Collapse
              size="small"
              items={parsedItems.map(item => ({
                key: item.code,
                label: (
                  <Space wrap>
                    <Typography.Text strong>{item.name}</Typography.Text>
                    <Tag color="blue">{item.category || '未分类'}</Tag>
                    <Tag>{item.latestDate}</Tag>
                    {item.sections.some(s => s.hasExcerpt) && <Tag color="orange">含重点</Tag>}
                    {item.sections.some(s => s.subSections.length > 0) && <Tag color="purple">{item.sections.reduce((n, s) => n + s.subSections.length, 0)}个子项</Tag>}
                  </Space>
                ),
                children: <RawSectionCollapse item={item} />,
              }))}
            />
          </Card>
        </>
      )}
    </div>
  );
}
