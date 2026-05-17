-- =====================================================
-- 如意面板 WAF CC防护模块
-- Author: lybbn
-- =====================================================

local _M = {
    _VERSION = '2.1.0'
}

local ngx = ngx
local ngx_shared = ngx.shared
local waf_utils = require("waf_utils")
local waf_init = require("waf_init")

local CC_CACHE_PREFIX = "cc:"
local ERROR_CACHE_PREFIX = "error:"
local TOLERANCE_CACHE_PREFIX = "tolerance:"
local BLOCK_CACHE_PREFIX = "cc_block:"

local function get_cache()
    return ngx_shared["waf_cache"]
end

local function get_cc_key(ip, request_type, url, ua)
    request_type = request_type or "ip"
    
    if request_type == "ip" then
        return waf_utils.get_cache_key(CC_CACHE_PREFIX, ip)
    elseif request_type == "url_no_param" then
        local url_path = url or ""
        -- 使用 plain 模式查找 ?，避免模式匹配
        local param_pos = string.find(url_path, "?", 1, true)
        if param_pos then
            url_path = string.sub(url_path, 1, param_pos - 1)
        end
        return waf_utils.get_cache_key(CC_CACHE_PREFIX, ip, url_path)
    elseif request_type == "url_with_param" then
        return waf_utils.get_cache_key(CC_CACHE_PREFIX, ip, url or "")
    elseif request_type == "ip_ua" then
        return waf_utils.get_cache_key(CC_CACHE_PREFIX, ip, ua or "")
    else
        return waf_utils.get_cache_key(CC_CACHE_PREFIX, ip)
    end
end

local function get_error_key(ip)
    return waf_utils.get_cache_key(ERROR_CACHE_PREFIX, ip)
end

local function get_tolerance_key(ip)
    return waf_utils.get_cache_key(TOLERANCE_CACHE_PREFIX, ip)
end

local function get_block_key(ip)
    return waf_utils.get_cache_key(BLOCK_CACHE_PREFIX, ip)
end

function _M.get_request_count(ip, window, request_type, url, ua)
    local cache = get_cache()
    if not cache then
        return 0
    end
    
    local key = get_cc_key(ip, request_type, url, ua)
    local count = cache:get(key)
    
    return tonumber(count) or 0
end

function _M.increment_request_count(ip, window, request_type, url, ua)
    local cache = get_cache()
    if not cache then
        return 0
    end
    
    local key = get_cc_key(ip, request_type, url, ua)
    local count, err = cache:incr(key, 1)
    
    if not count then
        cache:set(key, 1, window)
        count = 1
    end
    
    return count
end

function _M.get_error_count(ip, window)
    local cache = get_cache()
    if not cache then
        return 0
    end
    
    local key = get_error_key(ip)
    local count = cache:get(key)
    
    return tonumber(count) or 0
end

function _M.increment_error_count(ip, window)
    local cache = get_cache()
    if not cache then
        return 0
    end
    
    local key = get_error_key(ip)
    local count, err = cache:incr(key, 1)
    
    if not count then
        cache:set(key, 1, window)
        count = 1
    end
    
    return count
end

function _M.get_tolerance_count(ip)
    local cache = get_cache()
    if not cache then
        return 0
    end
    
    local key = get_tolerance_key(ip)
    local count = cache:get(key)
    
    return tonumber(count) or 0
end

function _M.increment_tolerance_count(ip)
    local cache = get_cache()
    if not cache then
        return 0
    end
    
    local key = get_tolerance_key(ip)
    local count, err = cache:incr(key, 1)
    
    if not count then
        cache:set(key, 1, 86400)
        count = 1
    end
    
    return count
end

-- 检查IP是否处于CC阻断状态
function _M.is_cc_blocked(ip)
    local cache = get_cache()
    if not cache then
        return false
    end
    
    local key = get_block_key(ip)
    local value = cache:get(key)
    
    return value ~= nil
end

-- 设置CC阻断状态
function _M.set_cc_blocked(ip, duration)
    local cache = get_cache()
    if not cache then
        return false
    end
    
    local key = get_block_key(ip)
    cache:set(key, "1", duration)
    
    return true
end

-- 清除CC阻断状态
function _M.clear_cc_blocked(ip)
    local cache = get_cache()
    if not cache then
        return false
    end
    
    local key = get_block_key(ip)
    cache:delete(key)
    
    return true
end

function _M.check_rate_limit(ip, site_id, host)
    local cc_config = waf_init.get_cc_config(site_id, host)
    
    if not cc_config then
        return false, nil
    end
    
    local frequency = cc_config.frequency or {}
    
    if not frequency.enabled then
        return false, nil
    end
    
    local window = frequency.period or 60
    local threshold = frequency.frequency or 100
    local block_duration = frequency.blockTime or 300
    local request_type = frequency.requestType or "ip"
    
    local url = waf_utils.get_request_uri()
    local ua = waf_utils.get_user_agent()
    
    local count = _M.get_request_count(ip, window, request_type, url, ua)
    
    if count > threshold then
        -- 设置IP阻断状态，在封锁时长内持续阻断
        if block_duration > 0 then
            _M.set_cc_blocked(ip, block_duration)
        end
        
        local reason = string.format("高频访问限制：%d 秒内请求%d次超过阈值%d", window, count, threshold)
        return true, reason, "frequency"
    end
    
    return false, nil
end

function _M.check_error_limit(ip, site_id, host)
    local cc_config = waf_init.get_cc_config(site_id, host)
    
    if not cc_config then
        return false, nil
    end
    
    local error_limit = cc_config.error_limit or {}
    
    if not error_limit.enabled then
        return false, nil
    end
    
    local window = error_limit.period or 60
    local threshold = error_limit.threshold or 10
    local block_duration = error_limit.blockTime or 600
    
    local count = _M.get_error_count(ip, window)
    
    if count >= threshold then
        -- 设置IP阻断状态
        if block_duration > 0 then
            _M.set_cc_blocked(ip, block_duration)
        end
        
        local reason = string.format("高频错误限制：%d 秒内触发错误%d次", window, count)
        return true, reason, "error_limit"
    end
    
    return false, nil
end

function _M.check_tolerance(ip, site_id, host)
    local cc_config = waf_init.get_cc_config(site_id, host)
    
    if not cc_config then
        return false, nil
    end
    
    local tolerance = cc_config.tolerance or {}
    
    if not tolerance.enabled then
        return false, nil
    end
    
    local threshold = tolerance.threshold or 3
    local block_duration = tolerance.blockTime or 3600
    
    local count = _M.get_tolerance_count(ip)
    
    if count >= threshold then
        -- 设置IP阻断状态
        if block_duration > 0 then
            _M.set_cc_blocked(ip, block_duration)
        end
        
        local reason = string.format("恶意容忍度超限：累计违规%d次", count)
        return true, reason, "tolerance"
    end
    
    return false, nil
end

function _M.record_violation(ip)
    _M.increment_tolerance_count(ip)
end

function _M.add_ip_to_blacklist(ip, duration, reason)
    if not ip or ip == "" then
        return false, "IP 地址为空"
    end
    
    -- 获取配置路径
    local waf_data_path = package.loaded.waf_data_path
    if not waf_data_path or waf_data_path == "" then
        waf_data_path = os.getenv("RUYI_WAF_DATA_PATH")
    end
    if not waf_data_path or waf_data_path == "" then
        waf_data_path = "/ruyi/data/waf"
    end
    
    -- 读取端口配置
    local port = 6789  -- 默认端口
    local port_file = waf_data_path .. "/port.ry"
    local port_f = io.open(port_file, "r")
    if port_f then
        local port_str = port_f:read("*a"):gsub("%s+$", "")
        port_f:close()
        local port_num = tonumber(port_str)
        if port_num and port_num > 0 and port_num < 65536 then
            port = port_num
        end
    end
    
    -- 读取 Token
    local token = ""
    local token_file = waf_data_path .. "/internal_token.ry"
    local token_f = io.open(token_file, "r")
    if token_f then
        token = token_f:read("*a"):gsub("%s+$", "")
        token_f:close()
    end
    
    -- 构建请求体
    local json = require("cjson.safe")
    local req_body = json.encode({
        ip = ip,
        list_type = "blacklist",
        remark = "CC 攻击自动拉黑：" .. (reason or "未知原因"),
        expire_at = os.date("%Y-%m-%d %H:%M:%S", ngx.now() + duration),
        enabled = true
    })
    
    -- 使用 TCP socket 发送请求
    local sock = ngx.socket.tcp()
    sock:settimeout(3000)
    
    local ok, err = sock:connect("127.0.0.1", port)
    if not ok then
        waf_utils.log_error("CC 攻击自动拉黑失败：连接失败 " .. (err or "unknown"))
        return false, err
    end
    
    local content_length = #req_body
    local request = string.format(
        "POST /api/waf/internal/?action=ip_blacklist HTTP/1.1\r\n" ..
        "Host: 127.0.0.1:%d\r\n" ..
        "Content-Type: application/json\r\n" ..
        "Content-Length: %d\r\n" ..
        "X-WAF-Token: %s\r\n" ..
        "Connection: close\r\n" ..
        "\r\n" ..
        "%s",
        port, content_length, token, req_body
    )
    
    local bytes, err = sock:send(request)
    if not bytes then
        waf_utils.log_error("CC 攻击自动拉黑失败：发送失败 " .. (err or "unknown"))
        sock:close()
        return false, err
    end
    
    local response, err = sock:receive("*a")
    sock:close()
    
    if not response then
        waf_utils.log_error("CC 攻击自动拉黑失败：接收失败 " .. (err or "unknown"))
        return false, err
    end
    
    local status = response:match("HTTP/%d%.%d%s+(%d+)")
    if status and tonumber(status) == 200 then
        waf_utils.log_info("CC 攻击自动拉黑成功：IP=" .. ip .. ", 时长=" .. duration .. "秒，原因=" .. (reason or ""))
        return true
    else
        waf_utils.log_error("CC 攻击自动拉黑失败：HTTP " .. (status or "unknown") .. ", IP=" .. ip)
        return false, "HTTP " .. (status or "unknown")
    end
end

-- 检查CC防护是否启用
-- 继承关系：检查cc_config中的三个子模块(frequency/error_limit/tolerance)
-- 任一模块启用则整体CC防护视为启用
function _M.is_cc_enabled(cc_config)
    if not cc_config then
        return false
    end
    
    -- 获取频率限制配置(继承自cc_config.frequency)
    local frequency = cc_config.frequency or {}
    -- 获取错误限制配置(继承自cc_config.error_limit)
    local error_limit = cc_config.error_limit or {}
    -- 获取容忍度配置(继承自cc_config.tolerance)
    local tolerance = cc_config.tolerance or {}
    
    -- 任一防护模块启用则返回true
    return (frequency.enabled == true) or 
           (error_limit.enabled == true) or 
           (tolerance.enabled == true)
end

function _M.check_cc_attack(ip, site_id, host)
    local cc_config = waf_init.get_cc_config(site_id, host)
    -- 注意：get_cc_config 已通过 get_effective_config 处理继承关系
    -- 如果站点 inherit_cc=false，返回站点配置；否则返回全局配置
    
    if not cc_config or not _M.is_cc_enabled(cc_config) then
        return false, nil
    end
    
    -- 首先检查IP是否已被CC阻断
    if _M.is_cc_blocked(ip) then
        return true, "CC防护：IP处于封锁状态", "blocked"
    end
    
    local rate_limit_blocked, rate_reason, rate_module = _M.check_rate_limit(ip, site_id, host)
    if rate_limit_blocked then
        return true, rate_reason, rate_module
    end
    
    local error_blocked, error_reason, error_module = _M.check_error_limit(ip, site_id, host)
    if error_blocked then
        return true, error_reason, error_module
    end
    
    local tolerance_blocked, tolerance_reason, tolerance_module = _M.check_tolerance(ip, site_id, host)
    if tolerance_blocked then
        return true, tolerance_reason, tolerance_module
    end
    
    return false, nil
end

function _M.check_request(site_id, host)
    local cdn_config = waf_init.get_cdn_config(site_id, host)
    local ip = waf_utils.get_real_ip_from_cdn(cdn_config)
    local url = waf_utils.get_request_uri()
    
    if waf_init.is_ip_in_whitelist(ip, host) then
        return false, nil
    end
    
    local cc_config = waf_init.get_cc_config(site_id, host)
    -- 注意：cc_config 已经包含继承逻辑处理后的最终配置
    -- 优先级：站点自定义配置 (inherit_cc=false) > 全局配置 (inherit_cc=true)
    
    if not cc_config or not _M.is_cc_enabled(cc_config) then
        return false, nil
    end
    
    -- 检查IP是否已被CC阻断（在计数之前检查，避免封锁期间仍计数）
    if _M.is_cc_blocked(ip) then
        return true, "CC防护：IP处于封锁状态", "blocked"
    end
    
    if cc_config.frequency and cc_config.frequency.enabled then
        local window = cc_config.frequency.period or 60
        local request_type = cc_config.frequency.requestType or "ip"
        local req_url = waf_utils.get_request_uri()
        local ua = waf_utils.get_user_agent()
        _M.increment_request_count(ip, window, request_type, req_url, ua)
    end
    
    local cc_blocked, cc_reason, cc_module = _M.check_cc_attack(ip, site_id, host)
    if cc_blocked then
        _M.record_violation(ip)
        return true, cc_reason, cc_module
    end
    
    return false, nil
end

return _M
