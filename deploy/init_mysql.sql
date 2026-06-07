CREATE DATABASE IF NOT EXISTS bp_prediction DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bp_prediction;
SET time_zone = '+08:00';

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('user', 'admin') NOT NULL DEFAULT 'user',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1=启用, 0=禁用',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

CREATE TABLE IF NOT EXISTS prediction_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    sbp_predicted INT NOT NULL COMMENT '预测收缩压 mmHg',
    dbp_predicted INT NOT NULL COMMENT '预测舒张压 mmHg',
    confidence DECIMAL(3,2) NOT NULL COMMENT '置信度 0.00~1.00',
    similar_count INT NOT NULL DEFAULT 0 COMMENT '相似样本数',
    avg_distance DECIMAL(8,4) NULL COMMENT '平均L2距离',
    explanation TEXT NULL COMMENT '预测解释文本',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='血压预测记录表';

CREATE TABLE IF NOT EXISTS ppg_raw_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    record_id BIGINT NOT NULL,
    signal_json LONGTEXT NOT NULL COMMENT 'PPG信号JSON数组',
    sample_rate INT NOT NULL DEFAULT 125,
    duration DECIMAL(4,1) NOT NULL DEFAULT 10.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES prediction_records(id) ON DELETE CASCADE,
    UNIQUE KEY uk_record_id (record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='PPG原始数据表';

CREATE TABLE IF NOT EXISTS system_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value VARCHAR(500) NOT NULL,
    description VARCHAR(255) NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

INSERT INTO system_configs (config_key, config_value, description) VALUES
('top_k_default', '5', 'Milvus相似检索默认Top-K值'),
('confidence_threshold', '0.6', '预测置信度阈值'),
('milvus_nprobe', '16', 'Milvus IVF索引nprobe参数'),
('snr_threshold', '10', 'PPG信号质量评估SNR阈值dB')
ON DUPLICATE KEY UPDATE
    config_value = VALUES(config_value),
    description = VALUES(description);

INSERT INTO users (username, email, password_hash, role, status) VALUES
('admin', 'admin@example.com', '$2b$12$fSf10yhp5Zk0KhwUd693AOml6MNTF8LjCuqikzm8P36Kci3RkrW.G', 'admin', 1)
ON DUPLICATE KEY UPDATE
    email = VALUES(email),
    password_hash = VALUES(password_hash),
    role = VALUES(role),
    status = VALUES(status);
