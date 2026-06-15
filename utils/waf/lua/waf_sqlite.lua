-- =====================================================
-- WAF 日志记录模块 (JSONL 文件模式)
-- 将攻击日志追加写入 JSONL 文件，由 Django 后台任务异步同步到数据库
-- 优点：面板重启/Worker崩溃不丢日志，支持断点续传
-- =====================================================

local _M = {
    _VERSION = '3.0.0'
}

local ngx = ngx
local ngx_log = ngx.log
local ngx_ERR = ngx.ERR
local ngx_INFO = ngx.INFO
local json = require("cjson.safe")

-- 文件轮转间隔（秒），默认300=5分钟
local ROTATE_INTERVAL = 300

-- 当前日志文件句柄及相关状态
local current_file = nil
local current_file_path = nil
local current_file_hour = nil

local function get_waf_data_path()
    local waf_data_path = package.loaded.waf_data_path
    if not waf_data_path or waf_data_path == "" then
        waf_data_path = os.getenv("RUYI_WAF_DATA_PATH")
    end
    if not waf_data_path or waf_data_path == "" then
        return nil
    end
    return waf_data_path
end

local function get_log_dir()
    local base = get_waf_data_path()
    if not base then
        return nil
    end
    return base .. "/logs"
end

local function ensure_log_dir(log_dir)
    if not log_dir then
        return false
    end
    -- 尝试创建目录并设置权限（确保www用户可写）
    local cmd = "mkdir -p \"" .. log_dir .. "\" 2>/dev/null || mkdir \"" .. log_dir .. "\" 2>/dev/null"
    local ok = os.execute(cmd)
    if ok then
        os.execute("chmod 777 \"" .. log_dir .. "\" 2>/dev/null")
        return true
    end
    -- 如果 os.execute 不可用，尝试用 io.open 间接验证
    local test_file = log_dir .. "/.test_write"
    local f = io.open(test_file, "w")
    if f then
        f:close()
        os.remove(test_file)
        return true
    end
    return false
end

local function get_current_hour()
    return math.floor(ngx.time() / ROTATE_INTERVAL)
end

local function build_file_path(log_dir)
    local timestamp = os.date("%Y%m%d%H%M%S", ngx.time())
    local pid = ngx.worker.pid()
    return log_dir .. "/waf_log_" .. timestamp .. "_" .. pid .. ".jsonl"
end

local function open_log_file()
    local log_dir = get_log_dir()
    if not log_dir then
        return nil, nil, "无法获取WAF数据路径"
    end

    if not ensure_log_dir(log_dir) then
        return nil, nil, "无法创建日志目录: " .. log_dir
    end

    local hour = get_current_hour()

    -- 如果当前文件句柄有效且未过期，直接复用
    if current_file and current_file_path and current_file_hour == hour then
        return current_file, current_file_path, nil
    end

    -- 需要打开新文件（首次调用或轮转到期）
    -- 先关闭旧文件
    if current_file then
        pcall(function() current_file:close() end)
        current_file = nil
        current_file_path = nil
        current_file_hour = nil
    end

    local file_path = build_file_path(log_dir)
    local f, err = io.open(file_path, "a")
    if not f then
        return nil, nil, "无法打开日志文件: " .. (err or "unknown")
    end

    -- 设置无缓冲写入，确保日志立即落盘
    f:setvbuf("no")

    current_file = f
    current_file_path = file_path
    current_file_hour = hour

    ngx_log(ngx_INFO, "[RUYI-WAF] 日志文件已打开: " .. file_path)

    return f, file_path, nil
end

local function close_log_file()
    if current_file then
        local path = current_file_path or "unknown"
        pcall(function()
            current_file:flush()
            current_file:close()
        end)
        current_file = nil
        current_file_path = nil
        current_file_hour = nil
        ngx_log(ngx_INFO, "[RUYI-WAF] 日志文件已关闭: " .. path)
    end
end

function _M.insert_attack_log(log_data)
    if not log_data then
        return false, "log_data is nil"
    end

    local f, file_path, err = open_log_file()
    if not f then
        ngx_log(ngx_ERR, "[RUYI-WAF] " .. err)
        return false, err
    end

    -- 序列化为单行 JSON
    local ok, json_str = pcall(json.encode, log_data)
    if not ok then
        ngx_log(ngx_ERR, "[RUYI-WAF] JSON序列化失败: " .. tostring(json_str))
        return false, "JSON encode failed"
    end

    -- 追加写入（JSONL格式：一行一个JSON对象 + 换行）
    local ok_write, err_write = pcall(function()
        f:write(json_str)
        f:write("\n")
        f:flush()  -- 立即刷盘确保不丢
    end)

    if not ok_write then
        ngx_log(ngx_ERR, "[RUYI-WAF] 日志写入失败: " .. tostring(err_write))
        -- 写入失败时关闭当前句柄，下次重试时会重新打开
        close_log_file()
        return false, tostring(err_write)
    end

    return true, nil
end

function _M.flush()
    -- JSONL模式下每条日志都立即刷盘，flush保持兼容
    if current_file then
        pcall(function() current_file:flush() end)
    end
    return true, nil
end

-- 兼容旧API（无操作）
function _M.set_buffer_size(size)
    -- JSONL模式不再需要缓冲区大小
end

function _M.set_buffer_timeout(timeout)
    -- JSONL模式不再需要缓冲区超时
end

function _M.set_api_host(host, port)
    -- JSONL模式不再需要API配置
end

function _M.test_connection()
    -- JSONL模式通过检测日志目录是否可写来验证
    local log_dir = get_log_dir()
    if not log_dir then
        return false, "无法获取WAF数据路径"
    end
    if not ensure_log_dir(log_dir) then
        return false, "无法创建日志目录"
    end
    return true, nil
end

-- close_log_file 由 Nginx exit_worker_by_lua_block 回调调用
return _M
