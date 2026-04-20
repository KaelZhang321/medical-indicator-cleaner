import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Statistic, Row, Col, Table, Tag, Space, Alert, Progress, message } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined, WarningOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { Radar } from '@antv/g2plot';
import { fetchFeatures } from '../api';

interface IndicatorFeature {
  code: string;
  name: string;
  category: string;
  latest_value: number | null;
  previous_value: number | null;
  change_rate: number | null;
  is_abnormal: boolean;
  trend: string;
  risk_level: string;
}

interface FeaturesSummary {
  total_indicators: number;
  abnormal_count: number;
  worsening_count: number;
  improving_count: number;
  new_abnormal_count: number;
  stable_abnormal_count: number;
  overall_trend: string;
}

interface FeaturesData {
  patient_id: string;
  exam_count: number;
  summary: FeaturesSummary;
  indicators: IndicatorFeature[];
  features: Record<string, number | null>;
}

const RISK_COLORS: Record<string, string> = {
  '恶化': 'red',
  '新增异常': 'volcano',
  '持续异常': 'orange',
  '改善': 'green',
  '正常': 'default',
};

const TREND_ICONS: Record<string, React.ReactNode> = {
  '上升': <ArrowUpOutlined style={{ color: '#ff4d4f' }} />,
  '下降': <ArrowDownOutlined style={{ color: '#52c41a' }} />,
  '稳定': <MinusOutlined style={{ color: '#999' }} />,
};

export default function FeaturesPage() {
  const [sfzh, setSfzh] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<FeaturesData | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<Radar | null>(null);

  const handleSearch = async () => {
    if (!sfzh.trim()) {
      message.warning('请输入身份证号');
      return;
    }
    setLoading(true);
    try {
      const result = await fetchFeatures(sfzh.trim()) as unknown as FeaturesData;
      setData(result);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '查询失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!data || !chartRef.current) return;

    const changeRates = data.indicators
      .filter(i => i.change_rate != null)
      .map(i => ({
        name: i.name,
        value: Math.abs(i.change_rate as number),
        direction: (i.change_rate as number) > 0 ? '上升' : '下降',
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);

    if (chartInstance.current) {
      chartInstance.current.destroy();
    }
    if (changeRates.length === 0) return;

    const chart = new Radar(chartRef.current, {
      data: changeRates,
      xField: 'name',
      yField: 'value',
      seriesField: 'direction',
      meta: { value: { alias: '变化率(绝对值)', min: 0 } },
      xAxis: { line: null, tickLine: null },
      yAxis: { grid: { alternateColor: ['rgba(0,0,0,0.02)', 'rgba(0,0,0,0)'] } },
      point: { size: 3 },
      area: {},
      legend: { position: 'top' },
    });
    chart.render();
    chartInstance.current = chart;
    return () => { chart.destroy(); };
  }, [data]);

  const s = data?.summary;
  const healthScore = s ? Math.max(0, Math.round(100 - s.abnormal_count * 3 - s.worsening_count * 5 - s.new_abnormal_count * 4 + s.improving_count * 2)) : 0;

  const changingIndicators = data?.indicators.filter(i => i.risk_level !== '正常' && i.risk_level !== '') || [];

  return (
    <div>
      <Space style={{ marginBottom: 24 }}>
        <Input
          placeholder="输入身份证号"
          value={sfzh}
          onChange={e => setSfzh(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 300 }}
        />
        <Button type="primary" onClick={handleSearch} loading={loading}>健康评估</Button>
      </Space>

      {data && s && (
        <>
          {/* 总体评估 */}
          <Alert
            message={`整体趋势：${s.overall_trend}`}
            description={`共 ${data.exam_count} 次体检，${s.total_indicators} 项数值指标。当前异常 ${s.abnormal_count} 项，其中恶化 ${s.worsening_count} 项、新增异常 ${s.new_abnormal_count} 项、改善 ${s.improving_count} 项。`}
            type={s.overall_trend === '整体好转' ? 'success' : s.overall_trend === '整体恶化' ? 'error' : 'warning'}
            showIcon
            style={{ marginBottom: 24 }}
          />

          {/* 核心统计 */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={4}>
              <Card><Statistic title="体检次数" value={data.exam_count} /></Card>
            </Col>
            <Col span={4}>
              <Card>
                <Statistic title="健康评分" value={healthScore} suffix="/ 100" valueStyle={{ color: healthScore >= 80 ? '#52c41a' : healthScore >= 60 ? '#faad14' : '#ff4d4f' }} />
                <Progress percent={healthScore} showInfo={false} strokeColor={healthScore >= 80 ? '#52c41a' : healthScore >= 60 ? '#faad14' : '#ff4d4f'} size="small" />
              </Card>
            </Col>
            <Col span={4}>
              <Card><Statistic title="异常指标" value={s.abnormal_count} valueStyle={{ color: s.abnormal_count > 0 ? '#ff4d4f' : '#52c41a' }} prefix={s.abnormal_count > 0 ? <WarningOutlined /> : <CheckCircleOutlined />} /></Card>
            </Col>
            <Col span={4}>
              <Card><Statistic title="恶化项" value={s.worsening_count} valueStyle={{ color: '#ff4d4f' }} /></Card>
            </Col>
            <Col span={4}>
              <Card><Statistic title="新增异常" value={s.new_abnormal_count} valueStyle={{ color: '#fa8c16' }} /></Card>
            </Col>
            <Col span={4}>
              <Card><Statistic title="改善项" value={s.improving_count} valueStyle={{ color: '#52c41a' }} /></Card>
            </Col>
          </Row>

          {/* 变化率雷达图 */}
          {data.indicators.some(i => i.change_rate != null) && (
            <Card title="指标变化率雷达图 (Top 10 变化最大)" style={{ marginBottom: 24 }}>
              <div ref={chartRef} style={{ height: 350 }} />
            </Card>
          )}

          {/* 需关注指标 */}
          <Card title={`需关注指标 (${changingIndicators.length} 项)`} style={{ marginBottom: 24 }}>
            <Table
              dataSource={changingIndicators}
              rowKey="code"
              size="small"
              pagination={false}
              columns={[
                { title: '指标名称', dataIndex: 'name', width: 180 },
                { title: '编码', dataIndex: 'code', width: 80 },
                { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color="blue">{c}</Tag> },
                { title: '最新值', dataIndex: 'latest_value', width: 90, render: (v: number | null) => v != null ? v.toFixed(2) : '-' },
                { title: '上次值', dataIndex: 'previous_value', width: 90, render: (v: number | null) => v != null ? v.toFixed(2) : '-' },
                {
                  title: '变化率', dataIndex: 'change_rate', width: 100,
                  render: (v: number | null) => {
                    if (v == null) return '-';
                    const pct = (v * 100).toFixed(1);
                    return <Tag color={v > 0.1 ? 'red' : v < -0.1 ? 'green' : 'default'}>{v > 0 ? '+' : ''}{pct}%</Tag>;
                  },
                },
                { title: '趋势', dataIndex: 'trend', width: 70, render: (t: string) => <span>{TREND_ICONS[t] || '-'} {t}</span> },
                {
                  title: '评估', dataIndex: 'risk_level', width: 100,
                  render: (r: string) => <Tag color={RISK_COLORS[r] || 'default'}>{r}</Tag>,
                  filters: [...new Set(changingIndicators.map(i => i.risk_level))].map(r => ({ text: r, value: r })),
                  onFilter: (value: any, record: IndicatorFeature) => record.risk_level === value,
                },
              ]}
            />
          </Card>

          {/* 全部指标明细 */}
          <Card title={`全部数值指标 (${data.indicators.length} 项)`}>
            <Table
              dataSource={data.indicators}
              rowKey="code"
              size="small"
              pagination={{ pageSize: 15, showTotal: t => `共 ${t} 项` }}
              rowClassName={record => record.is_abnormal ? 'row-abnormal' : ''}
              columns={[
                { title: '指标名称', dataIndex: 'name', width: 180 },
                { title: '编码', dataIndex: 'code', width: 80 },
                { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color="blue">{c}</Tag> },
                {
                  title: '最新值', dataIndex: 'latest_value', width: 90,
                  render: (v: number | null, r: IndicatorFeature) => (
                    <span style={{ color: r.is_abnormal ? '#ff4d4f' : undefined, fontWeight: r.is_abnormal ? 'bold' : undefined }}>
                      {v != null ? v.toFixed(2) : '-'}
                    </span>
                  ),
                },
                { title: '上次值', dataIndex: 'previous_value', width: 90, render: (v: number | null) => v != null ? v.toFixed(2) : '-' },
                {
                  title: '变化率', dataIndex: 'change_rate', width: 100,
                  sorter: (a: IndicatorFeature, b: IndicatorFeature) => Math.abs(a.change_rate ?? 0) - Math.abs(b.change_rate ?? 0),
                  render: (v: number | null) => {
                    if (v == null) return '-';
                    const pct = (v * 100).toFixed(1);
                    return <Tag color={v > 0.1 ? 'red' : v < -0.1 ? 'green' : 'default'}>{v > 0 ? '+' : ''}{pct}%</Tag>;
                  },
                },
                { title: '趋势', dataIndex: 'trend', width: 70, render: (t: string) => <span>{TREND_ICONS[t] || '-'} {t}</span> },
                {
                  title: '评估', dataIndex: 'risk_level', width: 100,
                  render: (r: string) => <Tag color={RISK_COLORS[r] || 'default'}>{r}</Tag>,
                  filters: [...new Set(data.indicators.map(i => i.risk_level))].map(r => ({ text: r, value: r })),
                  onFilter: (value: any, record: IndicatorFeature) => record.risk_level === value,
                },
              ]}
            />
          </Card>

          <style>{`
            .row-abnormal { background: #fff2f0 !important; }
            .row-abnormal:hover > td { background: #ffece8 !important; }
          `}</style>
        </>
      )}
    </div>
  );
}
