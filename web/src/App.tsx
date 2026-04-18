import { Layout, Menu } from 'antd';
import { SearchOutlined, LineChartOutlined, DotChartOutlined, ExperimentOutlined } from '@ant-design/icons';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import ExamPage from './pages/ExamPage';
import ComparisonPage from './pages/ComparisonPage';
import QuadrantPage from './pages/QuadrantPage';
import FeaturesPage from './pages/FeaturesPage';

const { Header, Content, Sider } = Layout;

const menuItems = [
  { key: '/', icon: <SearchOutlined />, label: '体检查询' },
  { key: '/comparison', icon: <LineChartOutlined />, label: '纵向对比' },
  { key: '/quadrant', icon: <DotChartOutlined />, label: '四象限分析' },
  { key: '/features', icon: <ExperimentOutlined />, label: '疗效预测' },
];

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth={0}>
        <div style={{ height: 32, margin: 16, color: '#fff', fontSize: 16, fontWeight: 'bold', textAlign: 'center' }}>
          指标标准化
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', fontSize: 18, fontWeight: 'bold' }}>
          HIS 体检指标标准化可视化系统
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8, minHeight: 360 }}>
          <Routes>
            <Route path="/" element={<ExamPage />} />
            <Route path="/comparison" element={<ComparisonPage />} />
            <Route path="/quadrant" element={<QuadrantPage />} />
            <Route path="/features" element={<FeaturesPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
