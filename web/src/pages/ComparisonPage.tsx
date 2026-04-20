import { useState, useRef, useEffect } from 'react';
import { Input, Button, Table, Tag, Select, Switch, Space, message } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { Line } from '@antv/g2plot';
import { fetchComparison, type ComparisonItem, type ComparisonResponse } from '../api';

export default function ComparisonPage() {
  const [sfzh, setSfzh] = useState('');
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [onlyAbnormal, setOnlyAbnormal] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<Line | null>(null);

  const handleSearch = async () => {
    if (!sfzh.trim()) {
      message.warning('请输入身份证号');
      return;
    }
    setLoading(true);
    try {
      const result = await fetchComparison(sfzh.trim(), category);
      setData(result);
      setSelectedCode(null);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '查询失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!data || !selectedCode || !chartRef.current) return;
    const item = data.comparisons.find(c => c.standard_code === selectedCode);
    if (!item) return;

    const chartData = data.exam_dates
      .filter(d => item.values[d] != null)
      .map(d => ({ date: d, value: item.values[d] as number }));

    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    const annotations: any[] = [];
    if (item.ref_min != null) {
      annotations.push({
        type: 'line',
        start: ['min', item.ref_min],
        end: ['max', item.ref_min],
        style: { stroke: '#52c41a', lineDash: [4, 4] },
        text: { content: `下限 ${item.ref_min}`, position: 'start', style: { fill: '#52c41a' } },
      });
    }
    if (item.ref_max != null) {
      annotations.push({
        type: 'line',
        start: ['min', item.ref_max],
        end: ['max', item.ref_max],
        style: { stroke: '#ff4d4f', lineDash: [4, 4] },
        text: { content: `上限 ${item.ref_max}`, position: 'start', style: { fill: '#ff4d4f' } },
      });
    }

    const chart = new Line(chartRef.current, {
      data: chartData,
      xField: 'date',
      yField: 'value',
      point: { size: 5, shape: 'circle' },
      label: { formatter: (d: any) => d.value?.toFixed(2) },
      annotations,
      meta: { value: { alias: `${item.standard_name} (${item.unit})` } },
    });
    chart.render();
    chartInstance.current = chart;

    return () => { chart.destroy(); };
  }, [data, selectedCode]);

  const categories = data ? [...new Set(data.comparisons.map(c => c.category))] : [];

  const columns: ColumnsType<ComparisonItem> = [
    { title: '指标', dataIndex: 'standard_name', width: 180 },
    { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color="blue">{c}</Tag> },
    { title: '单位', dataIndex: 'unit', width: 80 },
    ...(data?.exam_dates || []).map(date => ({
      title: date,
      key: date,
      width: 100,
      render: (_: any, record: ComparisonItem) => {
        const val = record.values[date];
        const isHigh = val != null && record.ref_max != null && val > record.ref_max;
        const isLow = val != null && record.ref_min != null && val < record.ref_min;
        return (
          <span style={{ color: isHigh ? '#ff4d4f' : isLow ? '#fa8c16' : undefined, fontWeight: isHigh || isLow ? 'bold' : undefined }}>
            {val != null ? val : '-'}
          </span>
        );
      },
    })),
    {
      title: '趋势',
      dataIndex: 'trend',
      width: 60,
      render: (t: string) => {
        const color = t === '↑' ? '#ff4d4f' : t === '↓' ? '#52c41a' : '#999';
        return <span style={{ fontSize: 18, color }}>{t || '-'}</span>;
      },
    },
    {
      title: '图表',
      width: 60,
      render: (_: any, record: ComparisonItem) => (
        <Button size="small" icon={<LineChartOutlined />} onClick={() => setSelectedCode(record.standard_code)} />
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 24 }} wrap>
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
          style={{ width: 150 }}
          value={category}
          onChange={setCategory}
          options={categories.map(c => ({ label: c, value: c }))}
        />
        <Button type="primary" onClick={handleSearch} loading={loading}>对比查询</Button>
        {data && (
          <Switch
            checkedChildren="仅看异常"
            unCheckedChildren="全部指标"
            checked={onlyAbnormal}
            onChange={setOnlyAbnormal}
          />
        )}
      </Space>

      {data && (
        <>
          <Table
            columns={columns}
            dataSource={onlyAbnormal ? data.comparisons.filter(c => {
              const latestDate = data.exam_dates[data.exam_dates.length - 1];
              const val = latestDate ? c.values[latestDate] : null;
              if (val == null) return false;
              return (c.ref_max != null && val > c.ref_max) || (c.ref_min != null && val < c.ref_min);
            }) : data.comparisons}
            rowKey="standard_code"
            size="small"
            pagination={{ pageSize: 15 }}
            scroll={{ x: 800 }}
          />
          {selectedCode && (
            <div style={{ marginTop: 24 }}>
              <h3>{data.comparisons.find(c => c.standard_code === selectedCode)?.standard_name} 变化趋势</h3>
              <div ref={chartRef} style={{ height: 300 }} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
