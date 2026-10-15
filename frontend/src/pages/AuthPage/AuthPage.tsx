import React, { useState } from 'react';
import { Card, Tabs, Form, Input, Button, message } from 'antd';
import { useAuth } from '@/context/AuthContext';

const AuthPage: React.FC = () => {
  const { login, register } = useAuth();
  const [activeTab, setActiveTab] = useState('login');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: { username: string; password: string; confirmPassword: string }) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      await register(values.username, values.password);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  const items = [
    {
      key: 'login',
      label: '老用户登录',
      children: (
        <Form onFinish={handleLogin} autoComplete="off">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password placeholder="密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            登录
          </Button>
        </Form>
      ),
    },
    {
      key: 'register',
      label: '新用户注册',
      children: (
        <Form onFinish={handleRegister} autoComplete="off">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password placeholder="密码" />
          </Form.Item>
          <Form.Item name="confirmPassword" rules={[{ required: true, message: '请确认密码' }]}>
            <Input.Password placeholder="确认密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            注册
          </Button>
        </Form>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#f0f2f5' }}>
      <Card title="EasyR 临床数据分析系统" style={{ width: 400 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} centered />
      </Card>
    </div>
  );
};

export default AuthPage;
