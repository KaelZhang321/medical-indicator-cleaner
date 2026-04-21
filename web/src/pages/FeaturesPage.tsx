import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Statistic, Row, Col, Table, Tag, Alert, Progress, Collapse, message } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined, WarningOutlined, CheckCircleOutlined, HeartOutlined, MedicineBoxOutlined } from '@ant-design/icons';
import { Radar } from '@antv/g2plot';
import { fetchFeatures, type FeaturesResponse, type IndicatorFeature } from '../api';

const RISK_COLORS: Record<string, string> = { '恶化': 'red', '新增异常': 'volcano', '持续异常': 'orange', '改善': 'green', '正常': 'default', '异常': 'orange' };
const STATUS_COLORS: Record<string, string> = { '正常': '#52c41a', '需关注': '#faad14', '异常': '#fa8c16', '危险': '#ff4d4f', '无数据': '#999' };
const TREND_ICONS: Record<string, React.ReactNode> = { '上升': <ArrowUpOutlined style={{ color: '#ff4d4f' }} />, '下降': <ArrowDownOutlined style={{ color: '#52c41a' }} />, '稳定': <MinusOutlined style={{ color: '#999' }} /> };

export default function FeaturesPage() {
  const [sfzh, setSfzh] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<FeaturesResponse | null>(null);
  const radarRef = useRef<HTMLDivElement>(null);
  const radarInstance = useRef<Radar | null>(null);

  const handleSearch = async () => {
    if (!sfzh.trim()) { message.warning('请输入身份证号'); return; }
    setLoading(true);
    try { setData(await fetchFeatures(sfzh.trim()) as FeaturesResponse); }
    catch (err: any) { message.error(err.response?.data?.detail || '查询失败'); setData(null); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (!data || !radarRef.current || !data.system_scores.length) return;
    const chartData = data.system_scores.map(s => ({ system: s.system, score: s.score }));
    if (radarInstance.current) radarInstance.current.destroy();
    const chart = new Radar(radarRef.current, {
      data: chartData, xField: 'system', yField: 'score',
      meta: { score: { alias: '系统评分', min: 0, max: 100 } },
      xAxis: { line: null, tickLine: null },
      yAxis: { grid: { alternateColor: ['rgba(0,0,0,0.02)', 'rgba(0,0,0,0)'] } },
      point: { size: 3 }, area: {},
    });
    chart.render();
    radarInstance.current = chart;
    return () => { chart.destroy(); };
  }, [data]);

  const s = data?.summary;
  const changingIndicators = data?.indicators.filter(i => i.risk_level !== '正常' && i.risk_level !== '') || [];

  return (
    <div className="page-shell">
      <div className="page-head">
        <div>
          <div className="page-kicker">Health Assessment</div>
          <h1 className="page-title">疗效预测</h1>
          <div className="page-subtitle">综合多次体检数据，按系统评估健康状态、识别风险趋势、计算衍生指标。</div>
        </div>
      </div>

      <Card className="query-panel" style={{ marginBottom: 24 }}>
        <div className="query-toolbar">
          <Input placeholder="输入身份证号" value={sfzh} onChange={e => setSfzh(e.target.value)} onPressEnter={handleSearch} style={{ width: 300 }} />
          <Button type="primary" onClick={handleSearch} loading={loading}>健康评估</Button>
        </div>
      </Card>

      {data && s && (
        <>
          <Alert
            message={`整体趋势：${s.overall_trend} | 数据跨度：${data.time_span || '—'}`}
            description={`共 ${data.exam_count} 次体检，${s.total_indicators} 项数值指标。当前异常 ${s.abnormal_count} 项，恶化 ${s.worsening_count} 项，改善 ${s.improving_count} 项。`}
            type={s.overall_trend === '整体好转' ? 'success' : s.overall_trend === '整体恶化' ? 'error' : 'warning'}
            showIcon style={{ marginBottom: 24 }}
          />

          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={5}>
              <Card>
                <div style={{ textAlign: 'center' }}>
                  <Progress type="dashboard" percent={data.overall_score} format={() => <span style={{ fontSize: 28, fontWeight: 'bold', color: data.overall_color }}>{data.overall_score}</span>} strokeColor={data.overall_color} size={120} />
                  <div style={{ marginTop: 8, fontSize: 16, fontWeight: 'bold', color: data.overall_color }}>{data.overall_level}</div>
                </div>
              </Card>
            </Col>
            <Col span={19}>
              <Row gutter={[16, 16]}>
                <Col span={6}><Card><Statistic title="体检次数" value={data.exam_count} /></Card></Col>
                <Col span={6}><Card><Statistic title="异常指标" value={s.abnormal_count} valueStyle={{ color: s.abnormal_count > 0 ? '#ff4d4f' : '#52c41a' }} prefix={s.abnormal_count > 0 ? <WarningOutlined /> : <CheckCircleOutlined />} /></Card></Col>
                <Col span={6}><Card><Statistic title="恶化项" value={s.worsening_count} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
                <Col span={6}><Card><Statistic title="改善项" value={s.improving_count} valueStyle={{ color: '#52c41a' }} /></Card></Col>
              </Row>
            </Col>
          </Row>

          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={12}>
              <Card title={<span><HeartOutlined /> 系统健康评分</span>}>
                {data.system_scores.length > 0 ? (
                  <>
                    <div ref={radarRef} style={{ height: 300 }} />
                    <Table dataSource={data.system_scores} rowKey="key" size="small" pagination={false}
                      columns={[
                        { title: '系统', dataIndex: 'system', width: 120 },
                        { title: '评分', dataIndex: 'score', width: 60, render: (v: number, r: any) => <span style={{ color: STATUS_COLORS[r.status] || '#999', fontWeight: 'bold' }}>{v}</span> },
                        { title: '状态', dataIndex: 'status', width: 80, render: (st: string) => <Tag color={STATUS_COLORS[st]}>{st}</Tag> },
                        { title: '趋势', dataIndex: 'trend', width: 80 },
                        { title: '异常数', dataIndex: 'abnormal_count', width: 60 },
                      ]}
                    />
                  </>
                ) : <div style={{ color: '#999', padding: 40, textAlign: 'center' }}>暂无系统评分数据</div>}
              </Card>
            </Col>
            <Col span={12}>
              {data.derived_indicators.length > 0 && (
                <Card title={<span><MedicineBoxOutlined /> 衍生临床指标</span>} style={{ marginBottom: 16 }}>
                  <Table dataSource={data.derived_indicators} rowKey="code" size="small" pagination={false}
                    columns={[
                      { title: '指标', dataIndex: 'name', width: 160 },
                      { title: '值', dataIndex: 'value', width: 60 },
                      { title: '参考', width: 80, render: (_: any, r: any) => r.ref_min != null && r.ref_max != null ? `${r.ref_min}-${r.ref_max}` : '-' },
                      { title: '状态', dataIndex: 'status', width: 60, render: (st: string) => <Tag color={st === '偏高' ? 'red' : st === '偏低' ? 'orange' : 'green'}>{st}</Tag> },
                      { title: '临床意义', dataIndex: 'clinical', ellipsis: true },
                    ]}
                  />
                </Card>
              )}
              {data.positive_changes.length > 0 && (
                <Card title={<span><CheckCircleOutlined style={{ color: '#52c41a' }} /> 改善项</span>}>
                  {data.positive_changes.map((c, i) => <Tag key={i} color="green" style={{ margin: 4 }}>{c}</Tag>)}
                </Card>
              )}
            </Col>
          </Row>

          {data.top_risks.length > 0 && (
            <Card className="section-card" title={<span><WarningOutlined style={{ color: '#ff4d4f' }} /> 风险关注项（{data.top_risks.length}项）</span>} style={{ marginBottom: 24 }}>
              <Collapse items={data.top_risks.map((r, idx) => ({
                key: `${r.code}-${idx}`,
                label: (
                  <span>
                    <Tag color={r.trend_type.includes('恶化') ? 'red' : r.trend_type === '波动不定' ? 'orange' : 'gold'}>{r.trend_type || '异常'}</Tag>
                    <strong>{r.name}</strong>
                    <span style={{ marginLeft: 8, color: '#999' }}>{r.value}{r.unit} | 连续异常{r.consecutive_abnormal}次 | 风险分{r.risk_score}</span>
                  </span>
                ),
                children: (
                  <div>
                    <p>趋势方向：{r.slope_direction}</p>
                    {r.predicted_6m != null && <p>6个月预测值：<strong>{r.predicted_6m}</strong></p>}
                    <p>分类：{r.category}</p>
                  </div>
                ),
              }))} />
            </Card>
          )}

          {changingIndicators.length > 0 && (
            <Card className="section-card table-card" title={`需关注指标 (${changingIndicators.length} 项)`} style={{ marginBottom: 24 }}>
              <Table dataSource={changingIndicators} rowKey="code" size="small" pagination={false}
                columns={[
                  { title: '指标名称', dataIndex: 'name', width: 180 },
                  { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color="blue">{c}</Tag> },
                  { title: '最新值', dataIndex: 'latest_value', width: 90, render: (v: number | null) => v != null ? v.toFixed(2) : '-' },
                  { title: '上次值', dataIndex: 'previous_value', width: 90, render: (v: number | null) => v != null ? v.toFixed(2) : '-' },
                  { title: '变化率', dataIndex: 'change_rate', width: 100, render: (v: number | null) => { if (v == null) return '-'; const pct = (v * 100).toFixed(1); return <Tag color={v > 0.1 ? 'red' : v < -0.1 ? 'green' : 'default'}>{v > 0 ? '+' : ''}{pct}%</Tag>; } },
                  { title: '趋势', dataIndex: 'trend', width: 70, render: (t: string) => <span>{TREND_ICONS[t] || '-'} {t}</span> },
                  { title: '评估', dataIndex: 'risk_level', width: 100, render: (r: string) => <Tag color={RISK_COLORS[r] || 'default'}>{r}</Tag> },
                ]}
              />
            </Card>
          )}

          <Card className="section-card table-card" title={`全部数值指标 (${data.indicators.length} 项)`}>
            <Table dataSource={data.indicators} rowKey="code" size="small" pagination={{ pageSize: 15, showTotal: t => `共 ${t} 项` }}
              rowClassName={(record: IndicatorFeature) => record.is_abnormal ? 'row-abnormal' : ''}
              columns={[
                { title: '指标名称', dataIndex: 'name', width: 180 },
                { title: '编码', dataIndex: 'code', width: 80 },
                { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color="blue">{c}</Tag> },
                { title: '最新值', dataIndex: 'latest_value', width: 90, render: (v: number | null, r: IndicatorFeature) => <span style={{ color: r.is_abnormal ? '#ff4d4f' : undefined, fontWeight: r.is_abnormal ? 'bold' : undefined }}>{v != null ? v.toFixed(2) : '-'}</span> },
                { title: '上次值', dataIndex: 'previous_value', width: 90, render: (v: number | null) => v != null ? v.toFixed(2) : '-' },
                { title: '变化率', dataIndex: 'change_rate', width: 100, sorter: (a: IndicatorFeature, b: IndicatorFeature) => Math.abs(a.change_rate ?? 0) - Math.abs(b.change_rate ?? 0), render: (v: number | null) => { if (v == null) return '-'; const pct = (v * 100).toFixed(1); return <Tag color={v > 0.1 ? 'red' : v < -0.1 ? 'green' : 'default'}>{v > 0 ? '+' : ''}{pct}%</Tag>; } },
                { title: '趋势', dataIndex: 'trend', width: 70, render: (t: string) => <span>{TREND_ICONS[t] || '-'} {t}</span> },
                { title: '评估', dataIndex: 'risk_level', width: 100, render: (r: string) => <Tag color={RISK_COLORS[r] || 'default'}>{r}</Tag>, filters: [...new Set(data.indicators.map(i => i.risk_level))].map(r => ({ text: r, value: r })), onFilter: (value: any, record: IndicatorFeature) => record.risk_level === value },
              ]}
            />
          </Card>

          {data.disclaimer && <Alert message={data.disclaimer} type="info" showIcon style={{ marginTop: 16 }} />}
        </>
      )}
    </div>
  );
}
