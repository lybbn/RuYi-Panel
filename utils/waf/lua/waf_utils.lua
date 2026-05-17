-- =====================================================
-- 如意面板 WAF 工具函数模块
-- Author: lybbn
-- =====================================================

local _M = {
    _VERSION = '1.0.0'
}

local bit = bit or require("bit")
local band = bit.band

local ngx = ngx
local ngx_var = ngx.var
local ngx_req = ngx.req
local ngx_log = ngx.log
local ngx_ERR = ngx.ERR
local ngx_WARN = ngx.WARN
local ngx_INFO = ngx.INFO
local ngx_exit = ngx.exit
local ngx_print = ngx.print
local ngx_encode_base64 = ngx.encode_base64
local ngx_decode_base64 = ngx.decode_base64
local ngx_md5 = ngx.md5
local string_find = string.find
local string_lower = string.lower
local string_upper = string.upper
local string_sub = string.sub
local string_len = string.len
local string_match = string.match
local string_gmatch = string.gmatch
local string_gsub = string.gsub
local string_format = string.format
local string_char = string.char
local string_byte = string.byte
local table_insert = table.insert
local table_concat = table.concat
local json = require("cjson.safe")

_M.json = json

function _M.log(level, msg)
    ngx_log(level, "[RUYI-WAF] " .. msg)
end

function _M.log_error(msg)
    _M.log(ngx_ERR, msg)
end

function _M.log_warn(msg)
    _M.log(ngx_WARN, msg)
end

function _M.log_info(msg)
    _M.log(ngx_INFO, msg)
end

function _M.get_client_ip()
    local headers = ngx_req.get_headers()
    local ip = headers["X-Real-IP"]
    
    if not ip or ip == "" then
        ip = headers["X-Forwarded-For"]
        if ip then
            local pos = string_find(ip, ",")
            if pos then
                ip = string_sub(ip, 1, pos - 1)
            end
        end
    end
    
    if not ip or ip == "" then
        ip = headers["X-Client-IP"]
    end
    
    if not ip or ip == "" then
        ip = ngx_var.remote_addr
    end
    
    return ip or "unknown"
end

function _M.get_user_agent()
    local headers = ngx_req.get_headers()
    return headers["User-Agent"] or ""
end

function _M.get_request_uri()
    return ngx_var.request_uri or ""
end

function _M.get_request_method()
    return ngx_req.get_method()
end

function _M.get_request_body()
    ngx_req.read_body()
    local body = ngx_req.get_body_data()
    if not body then
        local body_file = ngx_req.get_body_file()
        if body_file then
            local file = io.open(body_file, "r")
            if file then
                body = file:read("*a")
                file:close()
            end
        end
    end
    return body or ""
end

function _M.get_query_string()
    return ngx_var.query_string or ""
end

function _M.get_headers()
    return ngx_req.get_headers()
end

function _M.get_cookies()
    local headers = ngx_req.get_headers()
    return headers["Cookie"] or ""
end

function _M.get_referer()
    local headers = ngx_req.get_headers()
    return headers["Referer"] or ""
end

function _M.url_decode(str)
    if not str then return "" end
    str = string_gsub(str, "+", " ")
    str = string_gsub(str, "%%(%x%x)", function(h)
        return string_char(tonumber(h, 16))
    end)
    return str
end

function _M.url_encode(str)
    if not str then return "" end
    str = string_gsub(str, "([^%w%-%._~])", function(c)
        return string_format("%%%02X", string_byte(c))
    end)
    return str
end

function _M.html_escape(str)
    if not str then return "" end
    str = string_gsub(str, "&", "&amp;")
    str = string_gsub(str, "<", "&lt;")
    str = string_gsub(str, ">", "&gt;")
    str = string_gsub(str, '"', "&quot;")
    str = string_gsub(str, "'", "&#39;")
    return str
end

function _M.str_find(str, pattern, plain)
    if not str or not pattern then return nil end
    return string_find(string_lower(str), string_lower(pattern), 1, plain or false)
end

function _M.str_contains(str, pattern)
    return _M.str_find(str, pattern) ~= nil
end

function _M.str_starts_with(str, prefix)
    if not str or not prefix then return false end
    return string_sub(str, 1, string_len(prefix)) == prefix
end

function _M.str_ends_with(str, suffix)
    if not str or not suffix then return false end
    return string_sub(str, -string_len(suffix)) == suffix
end

function _M.regex_match(str, pattern)
    if not str or not pattern then return nil end
    local m = ngx.re.match(str, pattern, "joi")
    return m
end

function _M.regex_find_all(str, pattern)
    if not str or not pattern then return {} end
    local matches = {}
    local it, err = ngx.re.gmatch(str, pattern, "joi")
    if not it then return matches end
    while true do
        local m = it()
        if not m then break end
        table_insert(matches, m)
    end
    return matches
end

function _M.split(str, sep)
    local result = {}
    if not str then return result end
    local pattern = string_format("([^%s]+)", sep)
    for part in string_gmatch(str, pattern) do
        table_insert(result, part)
    end
    return result
end

function _M.trim(str)
    if not str then return "" end
    return string_match(str, "^%s*(.-)%s*$")
end

function _M.is_private_ip(ip)
    if not ip then return false end
    
    local private_ranges = {
        "^10%.",
        "^172%.(1[6-9]|2[0-9]|3[01])%.",
        "^192%.168%.",
        "^127%.",
        "^169%.254%.",
        "^::1$",
        "^fc00:",
        "^fe80:"
    }
    
    for _, pattern in ipairs(private_ranges) do
        if string_find(ip, pattern) then
            return true
        end
    end
    
    return false
end

function _M.ip_to_number(ip)
    if not ip then return 0 end
    local parts = _M.split(ip, ".")
    if #parts ~= 4 then return 0 end
    
    local num = 0
    for i, part in ipairs(parts) do
        num = num * 256 + tonumber(part) or 0
    end
    return num
end

function _M.ip_in_range(ip, range_start, range_end)
    local ip_num = _M.ip_to_number(ip)
    local start_num = _M.ip_to_number(range_start)
    local end_num = _M.ip_to_number(range_end)
    
    return ip_num >= start_num and ip_num <= end_num
end

function _M.ip_in_cidr(ip, cidr)
    if not ip or not cidr then return false end
    
    local cidr_parts = _M.split(cidr, "/")
    if #cidr_parts ~= 2 then return false end
    
    local network = cidr_parts[1]
    local prefix_len = tonumber(cidr_parts[2])
    
    if not prefix_len then return false end
    
    local ip_num = _M.ip_to_number(ip)
    local network_num = _M.ip_to_number(network)
    
    local mask = 0
    for i = 1, prefix_len do
        mask = mask * 2 + 1
    end
    for i = prefix_len + 1, 32 do
        mask = mask * 2
    end
    
    return band(ip_num, mask) == band(network_num, mask)
end

function _M.get_block_page_config()
    local waf_init = require("waf_init")
    local config = waf_init.load_global_config()
    if config and config.block_page_config then
        return config.block_page_config
    end
    return { show_detail = true, custom_page = "" }
end

function _M.block_request(status, msg, content_type)
    status = status or 403
    msg = msg or "Access Denied"
    content_type = content_type or "text/html; charset=utf-8"
    
    ngx.status = status
    ngx.header["Content-Type"] = content_type
    
    local block_config = _M.get_block_page_config()
    local show_detail = block_config.show_detail ~= false
    local custom_page = block_config.custom_page or ""
    
    -- 如果配置了自定义页面，返回自定义页面内容
    if custom_page and custom_page ~= "" then
        ngx_print(custom_page)
        ngx_exit(status)
        return
    end
    
    local detail_html = ""
    if show_detail then
        detail_html = '<div class="code">' .. _M.html_escape(msg) .. '</div>'
    end
    
    local html = [[
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>访问被拦截</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: #fff; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #e74c3c; margin-bottom: 20px; }
        p { color: #666; line-height: 1.6; }
        .code { background: #f8f8f8; padding: 10px; border-radius: 5px; font-family: monospace; margin: 20px 0; word-break: break-all; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ 访问被拦截</h1>
        <p>您的请求被安全防护系统拦截</p>
        ]] .. detail_html .. [[
        <p>如果您认为这是误判，请联系网站管理员</p>
    </div>
</body>
</html>
    ]]
    
    ngx_print(html)
    ngx_exit(status)
end

function _M.redirect(url, status)
    status = status or 302
    ngx.status = status
    ngx.header["Location"] = url
    ngx_exit(status)
end

function _M.json_response(data, status)
    status = status or 200
    ngx.status = status
    ngx.header["Content-Type"] = "application/json; charset=utf-8"
    ngx_print(json.encode(data))
    ngx_exit(status)
end

function _M.get_current_timestamp()
    return ngx.now()
end

function _M.format_timestamp(ts)
    return os.date("%Y-%m-%d %H:%M:%S", ts or ngx.now())
end

function _M.get_today_date()
    return os.date("%Y-%m-%d")
end

function _M.get_cache_key(prefix, ...)
    local parts = { prefix }
    local args = {...}
    for i = 1, #args do
        table_insert(parts, args[i])
    end
    return table_concat(parts, ":")
end

function _M.md5(str)
    return ngx_md5(str or "")
end

function _M.base64_encode(str)
    return ngx_encode_base64(str or "")
end

function _M.base64_decode(str)
    return ngx_decode_base64(str or "")
end

function _M.random_string(length)
    length = length or 16
    local chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    local result = {}
    for i = 1, length do
        local rand = math.random(1, #chars)
        table_insert(result, string_sub(chars, rand, rand))
    end
    return table_concat(result)
end

function _M.ip_to_number_fast(ip)
    if not ip or ip == "unknown" then
        return 0
    end
    
    local a, b, c, d = ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
    if not a then
        return 0
    end
    
    return tonumber(a) * 16777216 + tonumber(b) * 65536 + tonumber(c) * 256 + tonumber(d)
end

function _M.is_ip_in_geo_ranges(ip, ip_ranges)
    if not ip or ip == "unknown" or not ip_ranges or #ip_ranges == 0 then
        return false
    end
    
    local ip_num = _M.ip_to_number_fast(ip)
    if ip_num == 0 then
        return false
    end
    
    local left, right = 1, #ip_ranges
    
    while left <= right do
        local mid = math.floor((left + right) / 2)
        local entry = ip_ranges[mid]
        
        if ip_num >= entry.start and ip_num <= entry["end"] then
            return true
        elseif ip_num < entry.start then
            right = mid - 1
        else
            left = mid + 1
        end
    end
    
    return false
end

function _M.check_geo_restriction(ip, geo_config)
    if not geo_config or not geo_config.enabled then
        return false, nil
    end
    
    local mode = geo_config.mode or "whitelist"
    local ip_group_ids = geo_config.ip_groups or {}
    
    if not ip_group_ids or #ip_group_ids == 0 then
        return false, nil
    end
    
    local waf_init = require("waf_init")
    local ip_groups = waf_init.load_ip_groups()
    if not ip_groups or not ip_groups.groups then
        return false, nil
    end
    
    local all_ip_ranges = {}
    for _, group_id in ipairs(ip_group_ids) do
        local group = ip_groups.groups[tostring(group_id)]
        if group and group.ip_ranges then
            for _, r in ipairs(group.ip_ranges) do
                table.insert(all_ip_ranges, r)
            end
        end
    end
    
    if #all_ip_ranges == 0 then
        return false, nil
    end
    
    local is_in_ranges = _M.is_ip_in_geo_ranges(ip, all_ip_ranges)
    
    if mode == "whitelist" then
        if not is_in_ranges then
            return true, {
                type = "geo_restriction",
                reason = "地域限制：IP不在白名单中",
                matched_pattern = "地域白名单"
            }
        end
    elseif mode == "blacklist" then
        if is_in_ranges then
            return true, {
                type = "geo_restriction",
                reason = "地域限制：IP在黑名单中",
                matched_pattern = "地域黑名单"
            }
        end
    end
    
    return false, nil
end

function _M.get_real_ip_from_cdn(cdn_config)
    if not cdn_config or not cdn_config.enabled then
        return _M.get_client_ip()
    end
    
    local headers = cdn_config.headers or {"X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"}
    local ip_position = cdn_config.ip_position or "last"
    local headers_table = ngx_req.get_headers()
    
    for _, header in ipairs(headers) do
        local header_lower = string_lower(string_gsub(header, "-", "_"))
        local value = headers_table[header_lower]
        
        if value and value ~= "" then
            if type(value) == "table" then
                value = value[1]
            end
            
            if string_find(value, ",") then
                if ip_position == "first" then
                    local first_ip = string_match(value, "^([^,]+)")
                    if first_ip then
                        return _M.trim(first_ip)
                    end
                else
                    local last_ip = nil
                    for ip in string_gmatch(value, "([^,]+)") do
                        last_ip = ip
                    end
                    if last_ip then
                        return _M.trim(last_ip)
                    end
                end
            else
                return _M.trim(value)
            end
        end
    end
    
    return _M.get_client_ip()
end

function _M.is_cdn_ip(ip, cdn_config)
    if not cdn_config or not cdn_config.enabled then
        return false
    end
    
    local ip_group_ids = cdn_config.ip_groups or {}
    if not ip_group_ids or #ip_group_ids == 0 then
        return false
    end
    
    local waf_init = require("waf_init")
    local ip_groups = waf_init.load_ip_groups()
    if not ip_groups or not ip_groups.groups then
        return false
    end
    
    for _, group_id in ipairs(ip_group_ids) do
        local group = ip_groups.groups[tostring(group_id)]
        if group and group.ips then
            for _, cdn_ip in ipairs(group.ips) do
                if string_find(cdn_ip, "/") then
                    if _M.ip_in_cidr(ip, cdn_ip) then
                        return true
                    end
                else
                    if ip == cdn_ip then
                        return true
                    end
                end
            end
        end
    end
    
    return false
end

return _M
