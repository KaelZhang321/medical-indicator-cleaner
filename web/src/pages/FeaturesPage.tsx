import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Statistic, Row, Col, Table, Tag, Space, message } from 'antd';
import { Radar } from '@antv/g2plot';
import { fetchFeatures, type FeaturesResponse } from '../api';

export default function FeaturesPage() {
  const [sfzh, setSfzh] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<FeaturesResponse | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<Radar | null>(null);

  const handleSearch = async () => {
    if (!sfzh.trim()) {
      message.warning('请输入身份证号');
      return;
    }
    setLoading(true);
    try {
      const result = await fetchFeatures(sfzh.trim());
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

    // Select top change_rate features for radar chart
    const changeRates = Object.entries(data.features)
      .filter(([k, v]) => k.endsWith('_change_rate') && v != null)
      .map(([k, v]) => ({
        name: k.replace('_change_rate', ''),
        value: Math.abs(v as number),
        direction: (v as number) > 0 ? '上升' : '下降',
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);

    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    if (changeRates.length === 0) {
      return;
    }

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

  const latestFeatures = data
    ? Object.entries(data.features)
        .filter(([k]) => k.endsWith('_latest'))
        .map(([k, v]) => ({ code: k.replace('_latest', ''), value: v }))
    : [];

  const changeFeatures = data
    ? Object.entries(data.features)
        .filter(([k]) => k.endsWith('_change_rate'))
        .map(([k, v]) => ({
          code: k.replace('_change_rate', ''),
          change_rate: v,
        }))
        .sort((a, b) => Math.abs(b.change_rate ?? 0) - Math.abs(a.change_rate ?? 0))
    : [];

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
        <Button type="primary" onClick={handleSearch} loading={loading}>生成特征</Button>
      </Space>

      {data && (
        <>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={8}><Card><Statistic title="体检次数" value={data.exam_count} /></Card></Col>
            <Col span={8}><Card><Statistic title="异常指标数" value={data.features.abnormal_count ?? 0} valueStyle={{ color: (data.features.abnormal_count ?? 0) > 0 ? '#ff4d4f' : '#52c41a' }} /></Card></Col>
            <Col span={8}><Card><Statistic title="特征维度" value={Object.keys(data.features).length} /></Card></Col>
          </Row>

          {changeFeatures.length > 0 && (
            <Card title="指标变化率雷达图 (Top 10)" style={{ marginBottom: 24 }}>
              <div ref={chartRef} style={{ height: 350 }} />
            </Card>
          )}

          <Row gutter={16}>
            <Col span={12}>
              <Card title="最新值特征">
                <Table
                  dataSource={latestFeatures}
                  rowKey="code"
                  size="small"
                  pagination={{ pageSize: 10 }}
                  columns={[
                    { title: '指标编码', dataIndex: 'code', width: 120 },
                    { title: '最新值', dataIndex: 'value', render: (v: any) => v != null ? Number(v).toFixed(2) : '-' },
                  ]}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="变化率特征">
                <Table
                  dataSource={changeFeatures}
                  rowKey="code"
                  size="small"
                  pagination={{ pageSize: 10 }}
                  columns={[
                    { title: '指标编码', dataIndex: 'code', width: 120 },
                    {
                      title: '变化率',
                      dataIndex: 'change_rate',
                      render: (v: number | null) => {
                        if (v == null) return '-';
                        const pct = (v * 100).toFixed(1);
                        return <Tag color={v > 0.1 ? 'red' : v < -0.1 ? 'green' : 'default'}>{v > 0 ? '+' : ''}{pct}%</Tag>;
                      },
                    },
                  ]}
                />
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}
