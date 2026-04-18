import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Statistic, Row, Col, Table, Tag, Space, message } from 'antd';
import { Scatter } from '@antv/g2plot';
import { fetchQuadrant, type QuadrantResponse } from '../api';

const QUADRANT_COLORS: Record<string, string> = {
  '紧急处理': '#ff4d4f',
  '重点关注': '#fa8c16',
  '轻度异常': '#faad14',
  '正常范围': '#52c41a',
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

    const chartData: { name: string; deviation: number; risk_weight: number; quadrant: string; value: string }[] = [];
    for (const [quadrant, items] of Object.entries(data.quadrants)) {
      for (const item of items) {
        chartData.push({
          name: item.standard_name,
          deviation: Math.abs(item.deviation),
          risk_weight: item.risk_weight,
          quadrant,
          value: item.value != null ? `${item.value}` : '-',
        });
      }
    }

    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    const chart = new Scatter(chartRef.current, {
      data: chartData,
      xField: 'deviation',
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
        fields: ['name', 'deviation', 'risk_weight', 'value', 'quadrant'],
        formatter: (datum: any) => ({
          name: datum.name,
          value: `偏离=${datum.deviation.toFixed(2)}, 风险=${datum.risk_weight}, 值=${datum.value}`,
        }),
      },
      legend: { position: 'top' },
    });
    chart.render();
    chartInstance.current = chart;

    return () => { chart.destroy(); };
  }, [data]);

  const allItems = data
    ? Object.entries(data.quadrants).flatMap(([q, items]) => items.map(i => ({ ...i, quadrant: q })))
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

      {data && (
        <>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}><Card><Statistic title="紧急处理" value={data.stats.urgent_count} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
            <Col span={6}><Card><Statistic title="重点关注" value={data.stats.watch_count} valueStyle={{ color: '#fa8c16' }} /></Card></Col>
            <Col span={6}><Card><Statistic title="轻度异常" value={data.stats.mild_count} valueStyle={{ color: '#faad14' }} /></Card></Col>
            <Col span={6}><Card><Statistic title="正常范围" value={data.stats.normal_count} valueStyle={{ color: '#52c41a' }} /></Card></Col>
          </Row>

          <div ref={chartRef} style={{ height: 400, marginBottom: 24 }} />

          <Table
            dataSource={allItems}
            rowKey={(r, i) => `${r.standard_code}-${i}`}
            size="small"
            pagination={{ pageSize: 10 }}
            columns={[
              { title: '指标', dataIndex: 'standard_name', width: 180 },
              {
                title: '象限',
                dataIndex: 'quadrant',
                width: 100,
                render: (q: string) => <Tag color={QUADRANT_COLORS[q]}>{q}</Tag>,
                filters: Object.keys(QUADRANT_COLORS).map(k => ({ text: k, value: k })),
                onFilter: (value, record: any) => record.quadrant === value,
              },
              { title: '偏离度', dataIndex: 'deviation', width: 80, render: (v: number) => v.toFixed(2) },
              { title: '风险权重', dataIndex: 'risk_weight', width: 80 },
              { title: '值', dataIndex: 'value', width: 80 },
              { title: '参考下限', dataIndex: 'ref_min', width: 80, render: (v: any) => v ?? '-' },
              { title: '参考上限', dataIndex: 'ref_max', width: 80, render: (v: any) => v ?? '-' },
            ]}
          />
        </>
      )}
    </div>
  );
}
