import { useState, useRef, useEffect, useMemo } from 'react';
import { Alert, Card, Input, Button, Table, Tag, Select, Switch, Typography, message } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { Line } from '@antv/g2plot';
import { fetchComparison, type ComparisonItem, type ComparisonResponse } from '../api';

function isNumberValue(value: string | number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export default function ComparisonPage() {
  const [sfzh, setSfzh] = useState('');
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ComparisonResponse | null>(null);
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [onlyAbnormal, setOnlyAbnormal] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
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
      setChartError(null);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '查询失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const selectedItem = useMemo(
    () => (selectedCode && data ? data.comparisons.find(c => c.standard_code === selectedCode) ?? null : null),
    [data, selectedCode],
  );
  const chartData = useMemo(
    () => selectedItem && data
      ? data.exam_dates
        .filter(d => isNumberValue(selectedItem.values[d]))
        .map(d => ({ date: d, value: selectedItem.values[d] as number }))
      : [],
    [data, selectedItem],
  );

  useEffect(() => {
    if (!selectedItem || !chartRef.current) return;
    setChartError(null);

    if (chartInstance.current) {
      chartInstance.current.destroy();
      chartInstance.current = null;
    }

    if (chartData.length === 0) {
      return;
    }

    const annotations: any[] = [];
    if (selectedItem.ref_min != null) {
      annotations.push({
        type: 'line',
        start: ['min', selectedItem.ref_min],
        end: ['max', selectedItem.ref_min],
        style: { stroke: '#52c41a', lineDash: [4, 4] },
        text: { content: `下限 ${selectedItem.ref_min}`, position: 'start', style: { fill: '#52c41a' } },
      });
    }
    if (selectedItem.ref_max != null) {
      annotations.push({
        type: 'line',
        start: ['min', selectedItem.ref_max],
        end: ['max', selectedItem.ref_max],
        style: { stroke: '#ff4d4f', lineDash: [4, 4] },
        text: { content: `上限 ${selectedItem.ref_max}`, position: 'start', style: { fill: '#ff4d4f' } },
      });
    }

    try {
      const chart = new Line(chartRef.current, {
        data: chartData,
        xField: 'date',
        yField: 'value',
        point: { size: 5, shape: 'circle' },
        label: { formatter: (d: any) => d.value?.toFixed(2) },
        annotations,
        meta: { value: { alias: `${selectedItem.standard_name} (${selectedItem.unit})` } },
        smooth: true,
      });
      chart.render();
      chartInstance.current = chart;
    } catch (error) {
      console.error('comparison chart render failed', error);
      setChartError('图表渲染失败，请稍后重试或刷新页面。');
    }

    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
        chartInstance.current = null;
      }
    };
  }, [chartData, selectedItem]);

  const categories = data ? [...new Set(data.comparisons.map(c => c.category))] : [];

  const columns: ColumnsType<ComparisonItem> = [
    { title: '指标', dataIndex: 'standard_name', width: 180 },
    { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color="blue">{c}</Tag> },
    { title: '单位', dataIndex: 'unit', width: 80 },
    ...([...(data?.exam_dates || [])].reverse()).map(date => ({
      title: date,
      key: date,
      width: 100,
      render: (_: any, record: ComparisonItem) => {
        const val = record.values[date];
        const isHigh = isNumberValue(val) && record.ref_max != null && val > record.ref_max;
        const isLow = isNumberValue(val) && record.ref_min != null && val < record.ref_min;
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
    <div className="page-shell">
      <div className="page-head">
        <div>
          <div className="page-kicker">Longitudinal Numeric Comparison</div>
          <h1 className="page-title">纵向对比</h1>
          <div className="page-subtitle">按身份证号追踪数值指标的长期趋势，聚焦异常区间、变化方向和关键数值波动。</div>
        </div>
        <div className="page-status-chip">数值趋势 + 异常筛查</div>
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
        </div>
      </Card>

      {data && (
        <>
          <Card className="section-card table-card">
            <Table
              columns={columns}
              dataSource={onlyAbnormal ? data.comparisons.filter(c => {
                const latestDate = data.exam_dates[data.exam_dates.length - 1];
                const val = latestDate ? c.values[latestDate] : null;
                if (!isNumberValue(val)) return false;
                return (c.ref_max != null && val > c.ref_max) || (c.ref_min != null && val < c.ref_min);
              }) : data.comparisons}
              rowKey="standard_code"
              size="small"
              pagination={{ pageSize: 15 }}
              scroll={{ x: 800 }}
              onRow={(record) => ({
                onClick: () => {
                  setSelectedCode(record.standard_code);
                  setChartError(null);
                },
                style: { cursor: 'pointer' },
              })}
            />
          </Card>
          {selectedCode && (
            <Card className="section-card" style={{ marginTop: 24 }}>
              <Typography.Title level={4} style={{ marginTop: 0 }}>
                {selectedItem?.standard_name} 变化趋势
              </Typography.Title>
              {chartError ? (
                <Alert type="error" showIcon message={chartError} />
              ) : chartData.length === 0 ? (
                <Alert type="info" showIcon message="该指标暂无足够的数值数据用于绘制趋势图。" />
              ) : (
                <div ref={chartRef} style={{ height: 300 }} />
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
