import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Statistic, Row, Col, Table, Tag, Space, Alert, Progress, Collapse, message } from 'antd';
import { WarningOutlined, CheckCircleOutlined, MedicineBoxOutlined } from '@ant-design/icons';
import { Scatter } from '@antv/g2plot';
import { fetchQuadrant, type QuadrantResponse, type QuadrantItem } from '../api';

const QUADRANT_COLORS: Record<string, string> = {
  '紧急处理': '#ff4d4f',
  '重点关注': '#fa8c16',
  '轻度异常': '#faad14',
  '正常范围': '#52c41a',
};

const URGENCY_TAG: Record<string, { color: string; text: string }> = {
  urgent: { color: 'red', text: '紧急' },
  watch: { color: 'orange', text: '关注' },
  mild: { color: 'gold', text: '建议' },
  routine: { color: 'green', text: '正常' },
};

export default function QuadrantPage() {
  const [studyId, setStudyId] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<QuadrantResponse | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<Scatter | null>(null);

  const handleSearch = async () => {
    if (!studyId.trim()) {
      message.warning('请输入体检编号');
      return;
    }
    setLoading(true);
    try {
      const result = await fetchQuadrant(studyId.trim());
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

    const chartData: { name: string; abs_deviation: number; risk_weight: number; quadrant: string; value: string; category: string }[] = [];
    for (const [quadrant, items] of Object.entries(data.quadrants)) {
      for (const item of items) {
        chartData.push({
          name: item.standard_name,
          abs_deviation: item.abs_deviation,
          risk_weight: item.risk_weight,
          quadrant,
          value: item.value != null ? `${item.value}${item.unit}` : '-',
          category: item.category,
        });
      }
    }

    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    const chart = new Scatter(chartRef.current, {
      data: chartData,
      xField: 'abs_deviation',
      yField: 'risk_weight',
      colorField: 'quadrant',
      color: ['#52c41a', '#faad14', '#fa8c16', '#ff4d4f'],
      size: 6,
      shape: 'circle',
      pointStyle: { fillOpacity: 0.8, stroke: '#fff', lineWidth: 1 },
      xAxis: {
        title: { text: '偏离度 (|deviation|)' },
        grid: { line: { style: { lineDash: [4, 4] } } },
      },
      yAxis: {
        title: { text: '风险权重' },
        grid: { line: { style: { lineDash: [4, 4] } } },
      },
      annotations: [
        { type: 'line', start: [1, 'min'], end: [1, 'max'], style: { stroke: '#999', lineDash: [4, 4] } },
        { type: 'line', start: ['min', 0.7], end: ['max', 0.7], style: { stroke: '#999', lineDash: [4, 4] } },
        { type: 'text', position: [0.3, 0.85], content: '重点关注', style: { fill: '#fa8c16', fontSize: 14 } },
        { type: 'text', position: [1.5, 0.85], content: '紧急处理', style: { fill: '#ff4d4f', fontSize: 14 } },
        { type: 'text', position: [0.3, 0.35], content: '正常范围', style: { fill: '#52c41a', fontSize: 14 } },
        { type: 'text', position: [1.5, 0.35], content: '轻度异常', style: { fill: '#faad14', fontSize: 14 } },
      ],
      tooltip: {
        fields: ['name', 'abs_deviation', 'risk_weight', 'value', 'quadrant', 'category'],
        formatter: (datum: any) => ({
          name: `${datum.name} (${datum.category})`,
          value: `偏离=${datum.abs_deviation.toFixed(2)}, 风险=${datum.risk_weight}, 值=${datum.value}`,
        }),
      },
      legend: { position: 'top' },
    });
    chart.render();
    chartInstance.current = chart;

    return () => { chart.destroy(); };
  }, [data]);

  const hs = data?.health_score;
  const allItems = data
    ? Object.entries(data.quadrants).flatMap(([, items]) => items)
    : [];

  return (
    <div>
      <Space style={{ marginBottom: 24 }}>
        <Input
          placeholder="输入体检编号 (StudyID)"
          value={studyId}
          onChange={e => setStudyId(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 300 }}
        />
        <Button type="primary" onClick={handleSearch} loading={loading}>分析</Button>
      </Space>

      {data && hs && (
        <>
          {/* 健康评分 + 统计 */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <div style={{ textAlign: 'center' }}>
                  <Progress
                    type="dashboard"
                    percent={hs.score}
                    format={() => <span style={{ fontSize: 28, fontWeight: 'bold', color: hs.color }}>{hs.score}</span>}
                    strokeColor={hs.color}
                    size={120}
                  />
                  <div style={{ marginTop: 8, fontSize: 16, fontWeight: 'bold', color: hs.color }}>{hs.level}</div>
                </div>
              </Card>
            </Col>
            <Col span={18}>
              <Row gutter={16}>
                <Col span={6}><Card><Statistic title="紧急处理" value={data.stats.urgent_count} valueStyle={{ color: '#ff4d4f' }} prefix={<WarningOutlined />} /></Card></Col>
                <Col span={6}><Card><Statistic title="重点关注" value={data.stats.watch_count} valueStyle={{ color: '#fa8c16' }} /></Card></Col>
                <Col span={6}><Card><Statistic title="轻度异常" value={data.stats.mild_count} valueStyle={{ color: '#faad14' }} /></Card></Col>
                <Col span={6}><Card><Statistic title="正常范围" value={data.stats.normal_count} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} /></Card></Col>
              </Row>
              <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>共分析 {data.stats.total} 项数值指标</div>
            </Col>
          </Row>

          {/* 散点图 */}
          <Card title="四象限风险分布" style={{ marginBottom: 24 }}>
            <div ref={chartRef} style={{ height: 400 }} />
          </Card>

          {/* 健康建议 — Top 关注项 */}
          {data.top_concerns.length > 0 && (
            <Card
              title={<span><MedicineBoxOutlined /> 健康建议（{data.top_concerns.length} 项需关注）</span>}
              style={{ marginBottom: 24 }}
            >
              <Collapse
                items={data.top_concerns.map((item, idx) => {
                  const urgTag = URGENCY_TAG[item.advice.urgency] || URGENCY_TAG.routine;
                  return {
                    key: `${item.standard_code}-${idx}`,
                    label: (
                      <span>
                        <Tag color={QUADRANT_COLORS[item.quadrant]}>{item.quadrant}</Tag>
                        <Tag color={urgTag.color}>{urgTag.text}</Tag>
                        <strong>{item.standard_name}</strong>
                        <span style={{ marginLeft: 8, color: '#999' }}>
                          {item.value}{item.unit} (参考: {item.ref_min}-{item.ref_max})
                        </span>
                      </span>
                    ),
                    children: (
                      <div>
                        <p><strong>{item.advice.summary}</strong></p>
                        <p>建议行动：{item.advice.action}</p>
                        {item.advice.details.length > 0 && (
                          <ul>
                            {item.advice.details.map((d, i) => <li key={i}>{d}</li>)}
                          </ul>
                        )}
                      </div>
                    ),
                  };
                })}
              />
            </Card>
          )}

          {/* 全部指标明细 */}
          <Card title={`全部指标明细 (${allItems.length} 项)`}>
            <Table
              dataSource={allItems}
              rowKey={(r, i) => `${r.standard_code}-${i}`}
              size="small"
              pagination={{ pageSize: 15 }}
              rowClassName={record => record.quadrant === '紧急处理' || record.quadrant === '轻度异常' ? 'row-abnormal' : ''}
              columns={[
                { title: '指标', dataIndex: 'standard_name', width: 180 },
                { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color="blue">{c}</Tag> },
                {
                  title: '象限', dataIndex: 'quadrant', width: 100,
                  render: (q: string) => <Tag color={QUADRANT_COLORS[q]}>{q}</Tag>,
                  filters: Object.keys(QUADRANT_COLORS).map(k => ({ text: k, value: k })),
                  onFilter: (value: any, record: QuadrantItem) => record.quadrant === value,
                },
                {
                  title: '值', dataIndex: 'value', width: 100,
                  render: (v: number | null, r: QuadrantItem) => (
                    <span style={{ color: r.direction !== 'normal' ? '#ff4d4f' : undefined, fontWeight: r.direction !== 'normal' ? 'bold' : undefined }}>
                      {v != null ? v : '-'} {r.unit}
                    </span>
                  ),
                },
                { title: '参考范围', width: 120, render: (_: any, r: QuadrantItem) => r.ref_min != null && r.ref_max != null ? `${r.ref_min}-${r.ref_max}` : '-' },
                { title: '偏离度', dataIndex: 'abs_deviation', width: 80, sorter: (a: QuadrantItem, b: QuadrantItem) => a.abs_deviation - b.abs_deviation, render: (v: number) => v.toFixed(2) },
                { title: '风险权重', dataIndex: 'risk_weight', width: 80, sorter: (a: QuadrantItem, b: QuadrantItem) => a.risk_weight - b.risk_weight },
                {
                  title: '方向', dataIndex: 'direction', width: 60,
                  render: (d: string) => d === 'high' ? <Tag color="red">偏高</Tag> : d === 'low' ? <Tag color="orange">偏低</Tag> : <Tag color="green">正常</Tag>,
                },
              ]}
            />
          </Card>

          {/* 免责声明 */}
          <Alert
            message={data.disclaimer}
            type="info"
            showIcon
            style={{ marginTop: 16 }}
          />

          <style>{`
            .row-abnormal { background: #fff2f0 !important; }
            .row-abnormal:hover > td { background: #ffece8 !important; }
          `}</style>
        </>
      )}
    </div>
  );
}
