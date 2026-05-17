-- =====================================================
-- WAF 日志记录模块
-- 通过HTTP API将攻击日志写入Django后端数据库
-- =====================================================

local _M = {
    _VERSION = '2.0.0'
}

local ngx = ngx
local ngx_log = ngx.log
local ngx_ERR = ngx.ERR
local ngx_INFO = ngx.INFO
local json = require("cjson.safe")

local API_HOST = "127.0.0.1"
local API_PORT = nil
local API_PATH = "/api/waf/internal/?action=log"
local API_TOKEN = nil

local LOG_BUFFER = {}
local LOG_BUFFER_SIZE = 10
local LOG_BUFFER_TIMEOUT = 5
local last_flush_time = 0

local function get_api_port()
    if API_PORT then
        return API_PORT
    end
    
    local waf_data_path = package.loaded.waf_data_path
    if not waf_data_path or waf_data_path == "" then
        waf_data_path = os.getenv("RUYI_WAF_DATA_PATH")
    end
    
    if not waf_data_path or waf_data_path == "" then
        API_PORT = 6789
        return API_PORT
    end
    
    local port_file = waf_data_path .. "/port.ry"
    local file = io.open(port_file, "r")
    if file then
        local port_str = file:read("*a"):gsub("%s+$", "")
        file:close()
        local port = tonumber(port_str)
        if port and port > 0 and port < 65536 then
            API_PORT = port
            return API_PORT
        end
    end
    
    API_PORT = 6789
    return API_PORT
end

local function get_api_token()
    if API_TOKEN then
        return API_TOKEN
    end
    
    local waf_data_path = package.loaded.waf_data_path
    if not waf_data_path or waf_data_path == "" then
        waf_data_path = os.getenv("RUYI_WAF_DATA_PATH")
    end
    
    if not waf_data_path or waf_data_path == "" then
        return ""
    end
    
    local token_file = waf_data_path .. "/internal_token.ry"
    local file = io.open(token_file, "r")
    if file then
        API_TOKEN = file:read("*a"):gsub("%s+$", "")
        file:close()
        return API_TOKEN
    end
    
    return ""
end

local function send_http_request(body)
    local sock = ngx.socket.tcp()
    sock:settimeout(3000)
    
    local port = get_api_port()
    local ok, err = sock:connect(API_HOST, port)
    if not ok then
        ngx_log(ngx_ERR, "Failed to connect to API server: ", err)
        return false, err
    end
    
    local token = get_api_token()
    local content_length = #body
    
    local request = string.format(
        "POST %s HTTP/1.1\r\n" ..
        "Host: %s:%d\r\n" ..
        "Content-Type: application/json\r\n" ..
        "Content-Length: %d\r\n" ..
        "X-WAF-Token: %s\r\n" ..
        "Connection: close\r\n" ..
        "\r\n" ..
        "%s",
        API_PATH, API_HOST, port, content_length, token, body
    )
    
    local bytes, err = sock:send(request)
    if not bytes then
        ngx_log(ngx_ERR, "Failed to send request: ", err)
        sock:close()
        return false, err
    end
    
    local response, err = sock:receive("*a")
    sock:close()
    
    if not response then
        ngx_log(ngx_ERR, "Failed to receive response: ", err)
        return false, err
    end
    
    local status = response:match("HTTP/%d%.%d%s+(%d+)")
    if status and tonumber(status) >= 400 then
        ngx_log(ngx_ERR, "API returned error status: ", status)
        return false, "HTTP " .. status
    end
    
    return true, nil
end

local function send_logs_to_api(logs)
    if not logs or #logs == 0 then
        return true
    end
    
    local body = json.encode(logs)
    return send_http_request(body)
end

local function flush_buffer()
    if #LOG_BUFFER == 0 then
        return true
    end
    
    local logs_to_send = LOG_BUFFER
    LOG_BUFFER = {}
    
    local ok, err = send_logs_to_api(logs_to_send)
    if not ok then
        for _, log in ipairs(logs_to_send) do
            table.insert(LOG_BUFFER, log)
        end
        return false, err
    end
    
    return true, nil
end

local function should_flush()
    if #LOG_BUFFER >= LOG_BUFFER_SIZE then
        return true
    end
    
    local current_time = ngx.now()
    if current_time - last_flush_time >= LOG_BUFFER_TIMEOUT then
        return true
    end
    
    return false
end

function _M.insert_attack_log(log_data)
    table.insert(LOG_BUFFER, log_data)
    
    if should_flush() then
        local ok, err = flush_buffer()
        if not ok then
            ngx_log(ngx_ERR, "Failed to flush log buffer: ", err)
        end
        last_flush_time = ngx.now()
    end
    
    return true, nil
end

function _M.flush()
    return flush_buffer()
end

function _M.set_buffer_size(size)
    LOG_BUFFER_SIZE = size or 10
end

function _M.set_buffer_timeout(timeout)
    LOG_BUFFER_TIMEOUT = timeout or 5
end

function _M.set_api_host(host, port)
    API_HOST = host or "127.0.0.1"
    API_PORT = port or 6789
end

function _M.test_connection()
    local test_log = {
        {
            src_ip = "127.0.0.1",
            attack_type = "test",
            severity = "low",
            dst_url = "/test",
            action_taken = "log",
        }
    }
    return send_logs_to_api(test_log)
end

return _M
