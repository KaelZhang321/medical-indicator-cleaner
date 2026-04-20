import { ConfigProvider, Layout, Menu } from 'antd';
import { SearchOutlined, LineChartOutlined, DotChartOutlined, ExperimentOutlined } from '@ant-design/icons';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import ExamPage from './pages/ExamPage';
import ComparisonPage from './pages/ComparisonPage';
import TextComparisonPage from './pages/TextComparisonPage';
import TextComparisonOptimizedPage from './pages/TextComparisonOptimizedPage';
import QuadrantPage from './pages/QuadrantPage';
import FeaturesPage from './pages/FeaturesPage';

const { Header, Content, Sider } = Layout;

const menuItems = [
  { key: '/', icon: <SearchOutlined />, label: '体检查询' },
  { key: '/comparison', icon: <LineChartOutlined />, label: '纵向对比' },
  { key: '/text-comparison', icon: <LineChartOutlined />, label: '影像/结论对比' },
  { key: '/text-comparison-optimized', icon: <LineChartOutlined />, label: '影像/结论优化版' },
  { key: '/quadrant', icon: <DotChartOutlined />, label: '四象限分析' },
  { key: '/features', icon: <ExperimentOutlined />, label: '疗效预测' },
];

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout className="app-shell">
      <Sider breakpoint="lg" collapsedWidth={0} className="app-sider" width={280}>
        <div className="app-brand">
          <div className="app-brand-kicker">Clinical Review Workspace</div>
          <div className="app-brand-title">体检标准化</div>
          <div className="app-brand-subtitle">纵向对比、风险分层与影像结论解读</div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          className="app-menu"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout className="app-main">
        <Header className="app-header">
          <div className="app-header-content">
            <div className="app-header-eyebrow">HIS Medical Intelligence Console</div>
            <div className="app-header-title">HIS 体检指标标准化可视化系统</div>
            <div className="app-header-subtitle">面向医生与审核人员的体检数据工作台</div>
          </div>
        </Header>
        <Content className="app-content">
          <div className="content-surface">
            <Routes>
              <Route path="/" element={<ExamPage />} />
              <Route path="/comparison" element={<ComparisonPage />} />
              <Route path="/text-comparison" element={<TextComparisonPage />} />
              <Route path="/text-comparison-optimized" element={<TextComparisonOptimizedPage />} />
              <Route path="/quadrant" element={<QuadrantPage />} />
              <Route path="/features" element={<FeaturesPage />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#2d5b63',
          colorSuccess: '#4b7d67',
          colorWarning: '#c88a33',
          colorError: '#b84f3d',
          colorInfo: '#4d6f8f',
          colorText: '#24313a',
          colorTextSecondary: '#66707a',
          colorBorder: '#ddd4c5',
          colorBgLayout: '#f3ede3',
          colorBgContainer: '#fffdf9',
          borderRadius: 18,
          fontFamily: '"Avenir Next", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
          fontFamilyCode: '"SFMono-Regular", Consolas, Monaco, monospace',
        },
      }}
    >
      <BrowserRouter>
        <AppLayout />
      </BrowserRouter>
    </ConfigProvider>
  );
}
