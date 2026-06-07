-- 模拟用户数据 INSERT
-- 用于测试和演示环境初始化

INSERT INTO users (username, email, password_hash, role, status) VALUES
('zhangsan', 'zhangsan@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/I2K', 'user', 1),
('lisi', 'lisi@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/I2K', 'user', 1),
('wangwu', 'wangwu@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/I2K', 'user', 1),
('zhaoliu', 'zhaoliu@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/I2K', 'user', 1),
('admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/I2K', 'admin', 1);

-- 注：password_hash 是 "password123" 的 bcrypt 哈希值，仅用于测试
