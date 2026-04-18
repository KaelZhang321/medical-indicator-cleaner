import { useState } from 'react';
import { Input, Button, Table, Tag, Card, Descriptions, Statistic, Row, Col, Space, message } from 'antd';
import { SearchOutlined, WarningOutlined, CheckCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { fetchExam, type Indicator, type ExamResponse } from '../api';

export default function ExamPage() {
  const [studyId, setStudyId] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ExamResponse | null>(null);

  const handleSearch = async () => {
    if (!studyId.trim()) {
      message.warning('请输入体检编号');
      return;
    }
    setLoading(true);
    try {
      const result = await fetchExam(studyId.trim());
      setData(result);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '查询失败');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<Indicator> = [
    {
      title: '指标名称',
      dataIndex: 'standard_name',
      width: 200,
      filters: data ? [...new Set(data.indicators.map(i => i.category))].map(c => ({ text: c, value: c })) : [],
      onFilter: (value, record) => record.category === value,
    },
    {
      title: '编码',
      dataIndex: 'standard_code',
      width: 100,
    },
    {
      title: '分类',
      dataIndex: 'category',
      width: 120,
      render: (cat: string) => <Tag color="blue">{cat}</Tag>,
    },
    {
      title: '结果',
      dataIndex: 'value',
      width: 120,
      render: (val: any, record: Indicator) => (
        <span style={{ color: record.is_abnormal ? '#ff4d4f' : undefined, fontWeight: record.is_abnormal ? 'bold' : undefined }}>
          {val ?? '-'}
        </span>
      ),
    },
    {
      title: '单位',
      dataIndex: 'unit',
      width: 80,
    },
    {
      title: '参考范围',
      dataIndex: 'reference_range',
      width: 150,
      render: (val: string) => val && val !== 'nan' ? val : '-',
    },
    {
      title: '状态',
      width: 100,
      render: (_: any, record: Indicator) => {
        if (record.is_abnormal) {
          const color = record.abnormal_direction === 'high' ? 'red' : 'orange';
          const text = record.abnormal_direction === 'high' ? '偏高' : '偏低';
          return <Tag color={color} icon={<WarningOutlined />}>{text}</Tag>;
        }
        if (record.is_abnormal === false) {
          return <Tag color="green" icon={<CheckCircleOutlined />}>正常</Tag>;
        }
        return <Tag>-</Tag>;
      },
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 24 }}>
        <Input
          placeholder="输入体检编号 (StudyID)"
          value={studyId}
          onChange={e => setStudyId(e.target.value)}
          onPressEnter={handleSearch}
          style={{ width: 300 }}
          prefix={<SearchOutlined />}
        />
        <Button type="primary" onClick={handleSearch} loading={loading}>
          查询
        </Button>
      </Space>

      {data && (
        <>
          <Card style={{ marginBottom: 24 }}>
            <Descriptions title="基本信息" column={4}>
              <Descriptions.Item label="体检编号">{data.study_id}</Descriptions.Item>
              <Descriptions.Item label="姓名">{data.patient_name}</Descriptions.Item>
              <Descriptions.Item label="性别">{data.gender}</Descriptions.Item>
              <Descriptions.Item label="检查日期">{data.exam_time}</Descriptions.Item>
              <Descriptions.Item label="套餐" span={4}>{data.package_name}</Descriptions.Item>
            </Descriptions>
            <Row gutter={24} style={{ marginTop: 16 }}>
              <Col span={8}>
                <Statistic title="指标总数" value={data.summary.total_indicators} />
              </Col>
              <Col span={8}>
                <Statistic title="异常数" value={data.summary.abnormal_count} valueStyle={{ color: data.summary.abnormal_count > 0 ? '#ff4d4f' : '#52c41a' }} />
              </Col>
              <Col span={8}>
                <Statistic title="分类数" value={data.summary.categories.length} />
              </Col>
            </Row>
          </Card>

          <Table
            columns={columns}
            dataSource={data.indicators}
            rowKey={(r, i) => `${r.standard_code}-${i}`}
            size="small"
            pagination={{ pageSize: 20, showTotal: t => `共 ${t} 项` }}
            rowClassName={record => record.is_abnormal ? 'row-abnormal' : ''}
          />
        </>
      )}

      <style>{`
        .row-abnormal { background: #fff2f0 !important; }
        .row-abnormal:hover > td { background: #ffece8 !important; }
      `}</style>
    </div>
  );
}
