-- =====================================================
-- 如意面板 WAF 主检测模块
-- Author: lybbn
-- =====================================================

local _M = {
    _VERSION = '2.0.0'
}

local ngx = ngx
local ngx_var = ngx.var
local ngx_req = ngx.req
local ngx_log = ngx.log
local ngx_ERR = ngx.ERR
local ngx_INFO = ngx.INFO
local ngx_exit = ngx.exit
local ngx_print = ngx.print
local json = require("cjson.safe")
local waf_utils = require("waf_utils")
local waf_init = require("waf_init")
local waf_rules = require("waf_rules")
local waf_cc = require("waf_cc")
local waf_logger = require("waf_sqlite")

-- 静态资源扩展名模式（模块级常量，避免重复创建）
local STATIC_EXT_PATTERN = "%.(ico|png|jpe?g|gif|svg|css|js|woff2?|ttf|eot|otf|webp|map)$"

local function log_attack(attack_info)
    local log_data = {
        src_ip = attack_info.src_ip,
        src_location = attack_info.src_location or "",
        dst_url = attack_info.dst_url,
        dst_host = attack_info.dst_host,
        attack_type = attack_info.attack_type,
        severity = attack_info.severity or "medium",
        rule_id = attack_info.rule_id,
        rule_name = attack_info.rule_name,
        matched_pattern = attack_info.matched_pattern or "",
        action_taken = attack_info.action_taken or "observe",
        request_method = attack_info.request_method,
        user_agent = attack_info.user_agent,
        referer = attack_info.referer,
        raw_request = attack_info.raw_request or "",
        site_id = attack_info.site_id,
        request_id = ngx_var.request_id or "",
        headers = {}
    }
    
    local ok, err = waf_logger.insert_attack_log(log_data)
    if not ok then
        waf_utils.log_error("记录攻击日志失败: " .. (err or "unknown"))
    end
end

local function build_raw_request()
    local method = waf_utils.get_request_method()
    local url = waf_utils.get_request_uri()
    local headers = ngx_req.get_headers()
    
    local raw = method .. " " .. url .. " HTTP/1.1\r\n"
    for k, v in pairs(headers) do
        if type(v) == "table" then
            raw = raw .. k .. ": " .. table.concat(v, ", ") .. "\r\n"
        else
            raw = raw .. k .. ": " .. v .. "\r\n"
        end
    end
    
    return raw
end

local function get_severity_from_type(attack_type)
    local severity_map = {
        sql_injection = "high",
        xss = "high",
        command_injection = "critical",
        path_traversal = "high",
        file_include = "high",
        file_upload = "medium",
        sensitive_file = "high",
        scanner = "medium",
        cc_attack = "medium",
        ip_blacklist = "low",
        url_blacklist = "low",
        ua_blacklist = "low",
        geo_block = "low",
        request_limit = "medium"
    }
    return severity_map[attack_type] or "medium"
end

local function get_site_id()
    return ngx_var.site_id or nil
end

local function get_site_waf_status(site_id, host)
    local site_config = waf_init.get_site_config(site_id, host)
    if site_config then
        return site_config.waf_status or "off"
    end
    return waf_init.get_waf_status()
end

local function is_site_waf_enabled(site_id, host)
    local status = get_site_waf_status(site_id, host)
    return status ~= "off"
end

local function get_site_block_mode(site_id, host)
    local status = get_site_waf_status(site_id, host)
    return status == "protect"
end

function _M.handle_block(reason, attack_info, site_id, host)
    local is_block = get_site_block_mode(site_id, host)
    local cdn_config = waf_init.get_cdn_config(site_id, host)
    local ip = waf_utils.get_real_ip_from_cdn(cdn_config)
    local url = waf_utils.get_request_uri()
    
    attack_info = attack_info or {}
    attack_info.src_ip = ip
    attack_info.dst_url = url
    attack_info.dst_host = host or ngx_var.host or ""
    attack_info.attack_type = attack_info.type or "unknown"
    attack_info.severity = get_severity_from_type(attack_info.type)
    attack_info.request_method = waf_utils.get_request_method()
    attack_info.user_agent = waf_utils.get_user_agent()
    attack_info.referer = waf_utils.get_referer()
    attack_info.raw_request = build_raw_request()
    attack_info.site_id = site_id
    
    local waf_cc = require("waf_cc")
    waf_cc.record_violation(ip)
    
    local cc_config = waf_init.get_cc_config(site_id, host)
    
    -- 错误计数：每次拦截都增加错误计数
    if cc_config and cc_config.error_limit and cc_config.error_limit.enabled then
        local window = cc_config.error_limit.period or 60
        waf_cc.increment_error_count(ip, window)
    end
    
    -- CC 攻击自动拉黑逻辑
    -- 根据触发攻击的子模块的 blockTime 决定是否拉黑
    -- blockTime = 0: 不拉黑
    -- blockTime > 0: 拉黑，时长为 blockTime 秒
    if attack_info.attack_type == "cc_attack" and cc_config then
        local block_time = 0
        
        -- 判断是哪个子模块触发的攻击
        if attack_info.cc_module == "frequency" and cc_config.frequency then
            block_time = cc_config.frequency.blockTime or 0
        elseif attack_info.cc_module == "error_limit" and cc_config.error_limit then
            block_time = cc_config.error_limit.blockTime or 0
        elseif attack_info.cc_module == "tolerance" and cc_config.tolerance then
            block_time = cc_config.tolerance.blockTime or 0
        end
        
        -- blockTime > 0 时执行自动拉黑
        if block_time > 0 then
            waf_cc.add_ip_to_blacklist(ip, block_time, reason)
        end
    end
    
    if is_block then
        attack_info.action_taken = "block"
        log_attack(attack_info)
        waf_utils.block_request(403, reason)
        return true
    else
        attack_info.action_taken = "observe"
        log_attack(attack_info)
        waf_utils.log_warn("[观察模式] " .. reason)
        return false
    end
end

function _M.check_ip(site_id, host)
    local cdn_config = waf_init.get_cdn_config(site_id, host)
    local ip = waf_utils.get_real_ip_from_cdn(cdn_config)
    
    if waf_init.is_ip_whitelist_enabled() then
        if waf_init.is_ip_in_whitelist(ip, host) then
            return false, nil
        end
    end
    
    if waf_init.is_ip_blacklist_enabled() then
        local blocked, reason = waf_init.is_ip_in_blacklist(ip, host)
        if blocked then
            return true, {
                type = "ip_blacklist",
                reason = reason or "IP黑名单",
                matched_pattern = ip
            }
        end
    end
    
    return false, nil
end

function _M.check_url(site_id, host)
    local url = waf_utils.get_request_uri()
    
    if waf_init.is_url_whitelist_enabled() then
        if waf_init.is_url_in_whitelist(url) then
            return false, nil, true
        end
    end
    
    if waf_init.is_url_blacklist_enabled() then
        local blocked, item = waf_init.is_url_in_blacklist(url)
        if blocked then
            return true, {
                type = "url_blacklist",
                reason = "URL黑名单: " .. (item.url or url),
                response_code = item.response_code or 403,
                matched_pattern = item.url or url
            }
        end
    end
    
    return false, nil, false
end

function _M.check_ua(site_id, host)
    local ua = waf_utils.get_user_agent()
    
    if not ua or ua == "" then
        local request_limit_config = waf_init.get_request_limit_config(site_id, host)
        if request_limit_config and request_limit_config.enabled and request_limit_config.blockEmptyUA then
            return true, {
                type = "http_filter",
                reason = "空User-Agent被拦截",
                matched_pattern = "空UA"
            }
        end
    end
    
    if waf_init.is_ua_whitelist_enabled() then
        if waf_init.is_ua_in_whitelist(ua) then
            return false, nil
        end
    end
    
    if waf_init.is_ua_blacklist_enabled() then
        local blocked, item = waf_init.is_ua_in_blacklist(ua)
        if blocked then
            return true, {
                type = "ua_blacklist",
                reason = "UA黑名单: " .. (item.keyword or ""),
                matched_pattern = item.keyword or ua
            }
        end
    end
    
    return false, nil
end

function _M.check_request_limit(site_id, host)
    local config = waf_init.get_request_limit_config(site_id, host)
    
    if not config or not config.enabled then
        return false, nil
    end
    
    local method = waf_utils.get_request_method()
    local allowed_methods = config.allowedMethods or {"GET", "POST", "HEAD"}
    
    local method_allowed = false
    for _, m in ipairs(allowed_methods) do
        if string.upper(method) == string.upper(m) then
            method_allowed = true
            break
        end
    end
    
    if not method_allowed then
        return true, {
            type = "request_limit",
            reason = "HTTP方法不允许: " .. method,
            matched_pattern = method
        }
    end
    
    local host_header = ngx_var.host or ""
    if config.blockEmptyHost and host_header == "" then
        return true, {
            type = "request_limit",
            reason = "空Host头被拦截",
            matched_pattern = "空Host"
        }
    end
    
    local referer = waf_utils.get_referer()
    if config.blockEmptyReferer and (not referer or referer == "") then
        -- 排除静态资源文件，这些文件正常访问时可能没有Referer
        local uri = waf_utils.get_request_uri()
        if ngx.re.match(uri, STATIC_EXT_PATTERN, "ijo") then
            return false, nil
        end
        return true, {
            type = "request_limit",
            reason = "空Referer被拦截",
            matched_pattern = "空Referer"
        }
    end

    return false, nil
end

function _M.check_geo(site_id, host)
    local config = waf_init.get_geo_config(site_id, host)
    
    if not config or not config.enabled then
        return false, nil
    end
    
    local cdn_config = waf_init.get_cdn_config(site_id, host)
    local ip = waf_utils.get_real_ip_from_cdn(cdn_config)
    
    return waf_utils.check_geo_restriction(ip, config)
end

function _M.check_attack_rules(site_id, host)
    local rule_config = waf_init.get_rule_config(site_id, host)
    
    if not rule_config then
        return false, nil
    end
    
    local url = waf_utils.get_request_uri()
    local args = ngx_req.get_uri_args()
    local cookies = ngx_var.http_cookie or ""
    local ua = waf_utils.get_user_agent()
    local method = waf_utils.get_request_method()
    
    local function check_mode_enabled(rule_type)
        if not rule_config[rule_type] then
            return false
        end
        return rule_config[rule_type].mode ~= 0
    end
    
    local function check_rule_category(content, target, category_code, attack_type, attack_name)
        if not content or content == "" then
            return false, nil
        end
        
        local blocked, rule = waf_rules.check_rules_by_category(content, target, category_code)
        if blocked and rule then
            return true, {
                type = attack_type,
                reason = attack_name .. "(" .. target .. "): " .. rule.name,
                rule_id = rule.rule_id,
                rule_name = rule.name,
                matched_pattern = rule.pattern,
                severity = rule.severity
            }
        end
        return false, nil
    end
    
    local url_content = url
    for k, v in pairs(args) do
        if type(v) == "table" then
            url_content = url_content .. " " .. table.concat(v, " ")
        else
            url_content = url_content .. " " .. tostring(v)
        end
    end
    
    local categories = {
        {code = "sql", attack_type = "sql_injection", attack_name = "SQL注入检测", check_key = "sql"},
        {code = "xss", attack_type = "xss", attack_name = "XSS检测", check_key = "xss"},
        {code = "cmd", attack_type = "command_injection", attack_name = "命令注入检测", check_key = "command"},
        {code = "path", attack_type = "path_traversal", attack_name = "路径遍历检测", check_key = "file_include"},
        {code = "file", attack_type = "sensitive_file", attack_name = "敏感文件访问", check_key = "sensitive_file"},
        {code = "scan", attack_type = "scanner", attack_name = "扫描器检测", check_key = "scanner"},
        {code = "bot", attack_type = "bot", attack_name = "Bot检测", check_key = "bot"},
    }
    
    for _, cat in ipairs(categories) do
        if check_mode_enabled(cat.check_key) then
            local target = "url"
            if cat.code == "scan" or cat.code == "bot" then
                target = "header"
                local blocked, info = check_rule_category(ua, target, cat.code, cat.attack_type, cat.attack_name)
                if blocked then
                    return true, info
                end
            else
                local blocked, info = check_rule_category(url_content, target, cat.code, cat.attack_type, cat.attack_name)
                if blocked then
                    return true, info
                end
            end
        end
    end
    
    if (method == "POST" or method == "PUT" or method == "PATCH") then
        local body = waf_utils.get_request_body()
        if body and body ~= "" then
            for _, cat in ipairs(categories) do
                if check_mode_enabled(cat.check_key) and cat.code ~= "scan" and cat.code ~= "bot" and cat.code ~= "file" then
                    local blocked, info = check_rule_category(body, "post", cat.code, cat.attack_type, cat.attack_name)
                    if blocked then
                        return true, info
                    end
                end
            end
        end
    end
    
    if cookies ~= "" then
        for _, cat in ipairs(categories) do
            if check_mode_enabled(cat.check_key) and (cat.code == "sql" or cat.code == "xss") then
                local blocked, info = check_rule_category(cookies, "cookie", cat.code, cat.attack_type, cat.attack_name)
                if blocked then
                    return true, info
                end
            end
        end
    end
    
    return false, nil
end

function _M.check()
    local site_id = get_site_id()
    local host = ngx_var.host or ""
    
    if not is_site_waf_enabled(site_id, host) then
        return false
    end
    
    waf_init.init()
    
    local cdn_config = waf_init.get_cdn_config(site_id, host)
    local ip = waf_utils.get_real_ip_from_cdn(cdn_config)
    local url = waf_utils.get_request_uri()
    
    if waf_init.is_ip_whitelist_enabled() then
        if waf_init.is_ip_in_whitelist(ip, host) then
            return false
        end
    end
    
    local url_blocked, url_info, skip_checks = _M.check_url(site_id, host)
    if url_blocked then
        return _M.handle_block(url_info.reason, url_info, site_id, host)
    end
    
    if skip_checks then
        return false
    end
    
    local ip_blocked, ip_info = _M.check_ip(site_id, host)
    if ip_blocked then
        return _M.handle_block(ip_info.reason, ip_info, site_id, host)
    end
    
    local ua_blocked, ua_info = _M.check_ua(site_id, host)
    if ua_blocked then
        return _M.handle_block(ua_info.reason, ua_info, site_id, host)
    end
    
    local request_limit_blocked, request_limit_info = _M.check_request_limit(site_id, host)
    if request_limit_blocked then
        return _M.handle_block(request_limit_info.reason, request_limit_info, site_id, host)
    end
    
    local geo_blocked, geo_info = _M.check_geo(site_id, host)
    if geo_blocked then
        return _M.handle_block(geo_info.reason, geo_info, site_id, host)
    end
    
    local cc_blocked, cc_reason, cc_module = waf_cc.check_request(site_id, host)
    if cc_blocked then
        return _M.handle_block(cc_reason, { 
            type = "cc_attack", 
            reason = cc_reason,
            matched_pattern = "CC防护",
            cc_module = cc_module
        }, site_id, host)
    end
    
    local rule_blocked, rule_info = _M.check_attack_rules(site_id, host)
    if rule_blocked then
        return _M.handle_block(rule_info.reason, rule_info, site_id, host)
    end
    
    return false
end

function _M.init_worker()
    waf_utils.log_info("WAF Worker 初始化...")
    waf_init.init()
end

return _M
