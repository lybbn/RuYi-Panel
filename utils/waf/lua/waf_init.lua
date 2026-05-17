-- =====================================================
-- 如意面板 WAF 初始化模块
-- Author: lybbn
-- =====================================================

local _M = {
    _VERSION = '2.0.0'
}

local ngx = ngx
local ngx_shared = ngx.shared
local json = require("cjson.safe")
local waf_utils = require("waf_utils")

_M.global_config = {}
_M.site_configs = {}
_M.rules = {}
_M.ip_whitelist = {}
_M.ip_blacklist = {}
_M.url_whitelist = {}
_M.url_blacklist = {}
_M.ua_whitelist = {}
_M.ua_blacklist = {}
_M.site_ip_whitelist = {}
_M.site_ip_blacklist = {}
_M.ip_groups = {}

local CONFIG_CACHE_KEY = "waf:config"
local SITE_CONFIG_CACHE_KEY = "waf:site_config:"
local RULES_CACHE_KEY = "waf:rules"
local IP_WHITELIST_CACHE_KEY = "waf:ip_whitelist"
local IP_BLACKLIST_CACHE_KEY = "waf:ip_blacklist"
local URL_WHITELIST_CACHE_KEY = "waf:url_whitelist"
local URL_BLACKLIST_CACHE_KEY = "waf:url_blacklist"
local UA_WHITELIST_CACHE_KEY = "waf:ua_whitelist"
local UA_BLACKLIST_CACHE_KEY = "waf:ua_blacklist"
local SITE_IP_WHITELIST_CACHE_KEY = "waf:site_ip_whitelist"
local SITE_IP_BLACKLIST_CACHE_KEY = "waf:site_ip_blacklist"
local IP_GROUPS_CACHE_KEY = "waf:ip_groups"

local function get_waf_base_path()
    local package_path = package.path or ""
    local pos = string.find(package_path, "[/\\]utils[/\\]waf[/\\]lua")
    if pos then
        return string.sub(package_path, 1, pos - 1)
    end
    
    local prefix = ngx.config.prefix()
    if prefix then
        local panel_path = prefix
        if string.sub(panel_path, -1) == "/" or string.sub(panel_path, -1) == "\\" then
            panel_path = string.sub(panel_path, 1, -2)
        end
        local patterns = {
            "[/\\]server[/\\]nginx",
            "[/\\]server[/\\]ruyi",
            "[/\\]python[/\\]ruyi",
            "[/\\]ruyi"
        }
        for _, pattern in ipairs(patterns) do
            local found = string.find(panel_path, pattern)
            if found then
                if pattern == "[/\\]server[/\\]nginx" then
                    return string.sub(panel_path, 1, found + 6)
                end
                return string.sub(panel_path, 1, found + 5)
            end
        end
        if panel_path ~= "" and panel_path ~= "." then
            return panel_path
        end
    end
    
    return "/ruyi"
end

local function get_waf_data_path()
    if package.loaded.waf_data_path then
        return package.loaded.waf_data_path
    end
    
    return get_waf_base_path() .. "/data/waf"
end

local function get_config_path()
    return get_waf_data_path() .. "/config.json"
end

local function get_rules_path()
    return get_waf_data_path() .. "/rules.json"
end

local function get_ip_whitelist_path()
    return get_waf_data_path() .. "/ip_whitelist.json"
end

local function get_ip_blacklist_path()
    return get_waf_data_path() .. "/ip_blacklist.json"
end

local function get_url_whitelist_path()
    return get_waf_data_path() .. "/url_whitelist.json"
end

local function get_url_blacklist_path()
    return get_waf_data_path() .. "/url_blacklist.json"
end

local function get_ua_whitelist_path()
    return get_waf_data_path() .. "/ua_whitelist.json"
end

local function get_ua_blacklist_path()
    return get_waf_data_path() .. "/ua_blacklist.json"
end

local function get_site_ip_whitelist_path()
    return get_waf_data_path() .. "/site_ip_whitelist.json"
end

local function get_site_ip_blacklist_path()
    return get_waf_data_path() .. "/site_ip_blacklist.json"
end

local function get_ip_groups_path()
    return get_waf_data_path() .. "/ip_groups.json"
end

local function get_sites_dir()
    return get_waf_data_path() .. "/sites"
end

local function read_file(path)
    local file = io.open(path, "r")
    if not file then
        waf_utils.log_error("无法读取配置文件: " .. path)
        return nil
    end
    local content = file:read("*a")
    file:close()
    return content
end

local function load_json_file(path)
    local content = read_file(path)
    if not content then
        return nil
    end
    local data, err = json.decode(content)
    if not data then
        waf_utils.log_error("解析JSON失败: " .. path .. ", 错误: " .. (err or "unknown"))
        return nil
    end
    return data
end

local function get_cache()
    local cache = ngx_shared["waf_cache"]
    if not cache then
        waf_utils.log_warn("未配置共享内存区域 waf_cache，将使用内存存储")
    end
    return cache
end

function _M.load_global_config()
    local cache = get_cache()
    local config = nil
    
    if cache then
        local cached = cache:get(CONFIG_CACHE_KEY)
        if cached then
            local decoded = json.decode(cached)
            if decoded then
                _M.global_config = decoded
                return decoded
            end
        end
    end
    
    config = load_json_file(get_config_path())
    if config then
        _M.global_config = config
        if cache then
            cache:set(CONFIG_CACHE_KEY, json.encode(config), 60)
        end
    end
    
    return config or {}
end

function _M.load_site_config(site_id)
    local cache = get_cache()
    local cache_key = SITE_CONFIG_CACHE_KEY .. tostring(site_id)
    
    if cache then
        local cached = cache:get(cache_key)
        if cached then
            local decoded = json.decode(cached)
            if decoded then
                return decoded
            end
        end
    end
    
    local config_file = get_sites_dir() .. "/site_" .. tostring(site_id) .. ".json"
    local config = load_json_file(config_file)
    
    if config and cache then
        cache:set(cache_key, json.encode(config), 60)
    end
    
    return config
end

function _M.load_site_config_by_host(host)
    for site_id, config in pairs(_M.site_configs) do
        if config.site_name == host or config.domains then
            if config.domains then
                for _, domain in ipairs(config.domains) do
                    if domain == host then
                        return config
                    end
                end
            end
        end
    end
    return nil
end

function _M.load_all_site_configs()
    local sites_dir = io.popen('ls -1 "' .. get_sites_dir() .. '" 2>/dev/null')
    if not sites_dir then
        return
    end
    
    for filename in sites_dir:lines() do
        if string.match(filename, "^site_%d+%.json$") then
            local site_id = string.match(filename, "site_(%d+)%.json")
            if site_id then
                local config = _M.load_site_config(tonumber(site_id))
                if config then
                    _M.site_configs[tonumber(site_id)] = config
                end
            end
        end
    end
    sites_dir:close()
end

function _M.load_rules()
    local cache = get_cache()
    local rules = nil
    
    if cache then
        local cached = cache:get(RULES_CACHE_KEY)
        if cached then
            local decoded = json.decode(cached)
            if decoded then
                _M.rules = decoded
                return decoded
            end
        end
    end
    
    rules = load_json_file(get_rules_path())
    if rules then
        _M.rules = rules
        if cache then
            cache:set(RULES_CACHE_KEY, json.encode(rules), 60)
        end
    end
    
    return rules or {}
end

function _M.load_ip_whitelist()
    local whitelist = load_json_file(get_ip_whitelist_path())
    if whitelist then
        _M.ip_whitelist = whitelist
    end
    return whitelist or {}
end

function _M.load_ip_blacklist()
    local blacklist = load_json_file(get_ip_blacklist_path())
    if blacklist then
        _M.ip_blacklist = blacklist
    end
    return blacklist or {}
end

function _M.load_url_whitelist()
    local whitelist = load_json_file(get_url_whitelist_path())
    if whitelist then
        _M.url_whitelist = whitelist
    end
    return whitelist or {}
end

function _M.load_url_blacklist()
    local blacklist = load_json_file(get_url_blacklist_path())
    if blacklist then
        _M.url_blacklist = blacklist
    end
    return blacklist or {}
end

function _M.load_ua_whitelist()
    local whitelist = load_json_file(get_ua_whitelist_path())
    if whitelist then
        _M.ua_whitelist = whitelist
    end
    return whitelist or {}
end

function _M.load_ua_blacklist()
    local blacklist = load_json_file(get_ua_blacklist_path())
    if blacklist then
        _M.ua_blacklist = blacklist
    end
    return blacklist or {}
end

function _M.load_site_ip_whitelist()
    local whitelist = load_json_file(get_site_ip_whitelist_path())
    if whitelist then
        _M.site_ip_whitelist = whitelist
    end
    return whitelist or {}
end

function _M.load_site_ip_blacklist()
    local blacklist = load_json_file(get_site_ip_blacklist_path())
    if blacklist then
        _M.site_ip_blacklist = blacklist
    end
    return blacklist or {}
end

function _M.load_ip_groups()
    local cache = get_cache()
    
    if cache then
        local cached = cache:get(IP_GROUPS_CACHE_KEY)
        if cached then
            local decoded = json.decode(cached)
            if decoded then
                _M.ip_groups = decoded
                return decoded
            end
        end
    end
    
    local groups = load_json_file(get_ip_groups_path())
    if groups then
        _M.ip_groups = groups
        if cache then
            cache:set(IP_GROUPS_CACHE_KEY, json.encode(groups), 60)
        end
    end
    return groups or {}
end

function _M.init_worker()
    waf_utils.log_info("WAF Worker 初始化...")
    _M.init()
end

function _M.init()
    waf_utils.log_info("初始化 WAF 模块...")
    
    _M.load_global_config()
    _M.load_rules()
    _M.load_ip_whitelist()
    _M.load_ip_blacklist()
    _M.load_url_whitelist()
    _M.load_url_blacklist()
    _M.load_ua_whitelist()
    _M.load_ua_blacklist()
    _M.load_site_ip_whitelist()
    _M.load_site_ip_blacklist()
    _M.load_ip_groups()
    
    waf_utils.log_info("WAF 模块初始化完成")
end

function _M.clear_cache(cache_type)
    local cache = get_cache()
    if not cache then
        return false, "缓存不可用"
    end
    
    local cache_keys = {
        ip_whitelist = IP_WHITELIST_CACHE_KEY,
        ip_blacklist = IP_BLACKLIST_CACHE_KEY,
        url_whitelist = URL_WHITELIST_CACHE_KEY,
        url_blacklist = URL_BLACKLIST_CACHE_KEY,
        ua_whitelist = UA_WHITELIST_CACHE_KEY,
        ua_blacklist = UA_BLACKLIST_CACHE_KEY,
        site_ip_whitelist = SITE_IP_WHITELIST_CACHE_KEY,
        site_ip_blacklist = SITE_IP_BLACKLIST_CACHE_KEY,
        ip_groups = IP_GROUPS_CACHE_KEY,
        config = CONFIG_CACHE_KEY,
        rules = RULES_CACHE_KEY
    }
    
    if cache_type and cache_keys[cache_type] then
        cache:delete(cache_keys[cache_type])
        waf_utils.log_info("清除缓存: " .. cache_type)
    elseif cache_type == "all" or not cache_type then
        for name, key in pairs(cache_keys) do
            cache:delete(key)
        end
        cache:flush_all()
        waf_utils.log_info("清除所有缓存")
    end
    
    return true
end

function _M.reload()
    waf_utils.log_info("重新加载 WAF 配置...")
    
    _M.clear_cache("all")
    
    _M.init()
end

function _M.get_waf_status()
    local config = _M.global_config
    if not config then
        config = _M.load_global_config()
    end
    return config.waf_status or "off"
end

function _M.is_waf_enabled()
    local status = _M.get_waf_status()
    return status ~= "off"
end

function _M.get_waf_mode()
    local status = _M.get_waf_status()
    if status == "observe" then
        return "observe"
    elseif status == "protect" then
        return "block"
    end
    return "off"
end

function _M.is_block_mode()
    local status = _M.get_waf_status()
    return status == "protect"
end

function _M.is_observe_mode()
    local status = _M.get_waf_status()
    return status == "observe"
end

function _M.get_site_waf_status(site_id)
    local config = _M.load_site_config(site_id)
    if config then
        return config.waf_status or "off"
    end
    return _M.get_waf_status()
end

function _M.get_site_config(site_id, host)
    if site_id then
        local config = _M.load_site_config(site_id)
        if config then
            return config
        end
    end
    
    if host then
        local config = _M.load_site_config_by_host(host)
        if config then
            return config
        end
    end
    
    return nil
end

function _M.get_effective_config(site_id, host, config_name)
    local site_config = _M.get_site_config(site_id, host)
    
    if site_config then
        local inherit_status = site_config.inherit_status or {}
        local inherit_key = config_name:gsub("_config", "")
        
        if inherit_status[inherit_key] == false then
            return site_config[config_name] or {}
        end
    end
    
    local global_config = _M.global_config
    if not global_config or not next(global_config) then
        global_config = _M.load_global_config()
    end
    
    return global_config[config_name] or {}
end

function _M.get_cc_config(site_id, host)
    return _M.get_effective_config(site_id, host, "cc_config")
end

function _M.get_geo_config(site_id, host)
    return _M.get_effective_config(site_id, host, "geo_config")
end

function _M.get_request_limit_config(site_id, host)
    return _M.get_effective_config(site_id, host, "request_limit_config")
end

function _M.get_rule_config(site_id, host)
    return _M.get_effective_config(site_id, host, "rule_config")
end

function _M.get_cdn_config(site_id, host)
    local site_config = _M.get_site_config(site_id, host)
    if site_config and site_config.cdn_config then
        return site_config.cdn_config
    end
    return {}
end

function _M.get_access_control_config()
    local config = _M.global_config
    if not config then
        config = _M.load_global_config()
    end
    return config.access_control or {}
end

function _M.is_ip_whitelist_enabled()
    local access_control = _M.get_access_control_config()
    return access_control.ip_whitelist_enabled ~= false
end

function _M.is_ip_blacklist_enabled()
    local access_control = _M.get_access_control_config()
    return access_control.ip_blacklist_enabled ~= false
end

function _M.is_url_whitelist_enabled()
    local access_control = _M.get_access_control_config()
    return access_control.url_whitelist_enabled ~= false
end

function _M.is_url_blacklist_enabled()
    local access_control = _M.get_access_control_config()
    return access_control.url_blacklist_enabled ~= false
end

function _M.is_ua_whitelist_enabled()
    local access_control = _M.get_access_control_config()
    return access_control.ua_whitelist_enabled ~= false
end

function _M.is_ua_blacklist_enabled()
    local access_control = _M.get_access_control_config()
    return access_control.ua_blacklist_enabled ~= false
end

function _M.is_ip_in_whitelist(ip, host)
    local whitelist = _M.load_ip_whitelist()
    
    if not whitelist.enabled then
        return false
    end
    
    local site_whitelist = _M.load_site_ip_whitelist()
    
    if site_whitelist and host then
        local site_data = site_whitelist[host]
        if site_data and site_data.ips then
            for _, item in ipairs(site_data.ips) do
                if item.ip == ip then
                    return true
                end
                if item.cidr and waf_utils.ip_in_cidr(ip, item.cidr) then
                    return true
                end
            end
        end
    end
    
    if whitelist and whitelist.ips then
        for _, item in ipairs(whitelist.ips) do
            if item.ip == ip then
                return true
            end
            if item.cidr and waf_utils.ip_in_cidr(ip, item.cidr) then
                return true
            end
        end
    end
    
    return false
end

function _M.is_ip_in_blacklist(ip, host)
    local blacklist = _M.load_ip_blacklist()
    
    if not blacklist.enabled then
        return false
    end
    
    local site_blacklist = _M.load_site_ip_blacklist()
    
    if site_blacklist and host then
        local site_data = site_blacklist[host]
        if site_data and site_data.ips then
            for _, item in ipairs(site_data.ips) do
                if item.ip == ip then
                    return true, item.remark or "站点黑名单IP"
                end
                if item.cidr and waf_utils.ip_in_cidr(ip, item.cidr) then
                    return true, item.remark or "站点黑名单IP段"
                end
            end
        end
    end
    
    if blacklist and blacklist.ips then
        for _, item in ipairs(blacklist.ips) do
            if item.ip == ip then
                return true, item.remark or "黑名单IP"
            end
            if item.cidr and waf_utils.ip_in_cidr(ip, item.cidr) then
                return true, item.remark or "黑名单IP段"
            end
        end
    end
    
    return false
end

function _M.is_url_in_whitelist(url)
    local whitelist = _M.load_url_whitelist()
    
    if not whitelist.enabled then
        return false
    end
    
    if not whitelist.urls then
        return false
    end
    
    for _, item in ipairs(whitelist.urls) do
        if item.match_type == "exact" and url == item.url then
            return true
        elseif item.match_type == "prefix" and waf_utils.str_starts_with(url, item.url) then
            return true
        elseif item.match_type == "suffix" and waf_utils.str_ends_with(url, item.url) then
            return true
        elseif item.match_type == "regex" then
            local m = waf_utils.regex_match(url, item.url)
            if m then
                return true
            end
        end
    end
    
    return false
end

function _M.is_url_in_blacklist(url)
    local blacklist = _M.load_url_blacklist()
    
    if not blacklist.enabled then
        return false, nil
    end
    
    if not blacklist.urls then
        return false, nil
    end
    
    for _, item in ipairs(blacklist.urls) do
        local matched = false
        if item.match_type == "exact" and url == item.url then
            matched = true
        elseif item.match_type == "prefix" and waf_utils.str_starts_with(url, item.url) then
            matched = true
        elseif item.match_type == "suffix" and waf_utils.str_ends_with(url, item.url) then
            matched = true
        elseif item.match_type == "regex" then
            local m = waf_utils.regex_match(url, item.url)
            if m then
                matched = true
            end
        end
        
        if matched then
            return true, item
        end
    end
    
    return false, nil
end

function _M.is_ua_in_whitelist(ua)
    local whitelist = _M.load_ua_whitelist()
    
    if not whitelist.enabled then
        return false
    end
    
    if not whitelist.keywords then
        return false
    end
    
    for _, item in ipairs(whitelist.keywords) do
        if waf_utils.str_contains(ua, item.keyword) then
            return true
        end
    end
    
    return false
end

function _M.is_ua_in_blacklist(ua)
    local blacklist = _M.load_ua_blacklist()
    
    if not blacklist.enabled then
        return false, nil
    end
    
    if not blacklist.keywords then
        return false, nil
    end
    
    for _, item in ipairs(blacklist.keywords) do
        if waf_utils.str_contains(ua, item.keyword) then
            return true, item
        end
    end
    
    return false, nil
end

function _M.get_rules_by_category(category)
    local rules = _M.rules
    if not rules then
        rules = _M.load_rules()
    end
    
    local result = {}
    if not rules or not rules.rules then
        return result
    end
    
    for _, rule in ipairs(rules.rules) do
        if rule.enabled and (not category or rule.category == category) then
            table.insert(result, rule)
        end
    end
    
    return result
end

function _M.get_config_value(key, default)
    local config = _M.global_config
    if not config then
        config = _M.load_global_config()
    end
    
    local value = config[key]
    if value == nil then
        return default
    end
    return value
end

function _M.is_cdn_ip(ip, site_id, host)
    local cdn_config = _M.get_cdn_config(site_id, host)
    
    if not cdn_config or not cdn_config.enabled then
        return false
    end
    
    local ip_group_ids = cdn_config.ip_groups or {}
    if not ip_group_ids or #ip_group_ids == 0 then
        return false
    end
    
    local ip_groups = _M.load_ip_groups()
    if not ip_groups or not ip_groups.groups then
        return false
    end
    
    for _, group_id in ipairs(ip_group_ids) do
        local group = ip_groups.groups[tostring(group_id)]
        if group and group.ips then
            for _, cdn_ip in ipairs(group.ips) do
                if cdn_ip == ip then
                    return true
                end
                if waf_utils.ip_in_cidr(ip, cdn_ip) then
                    return true
                end
            end
        end
    end
    
    return false
end

function _M.get_real_ip(site_id, host)
    local cdn_config = _M.get_cdn_config(site_id, host)
    
    if not cdn_config or not cdn_config.enabled then
        return waf_utils.get_client_ip()
    end
    
    local headers = cdn_config.headers or {"X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP"}
    local ip_position = cdn_config.ip_position or "last"
    
    for _, header in ipairs(headers) do
        local value = ngx.var["http_" .. string.lower(string.gsub(header, "-", "_"))]
        if value and value ~= "" then
            if string_find(value, ",") then
                if ip_position == "first" then
                    local first_ip = string.match(value, "^([^,]+)")
                    if first_ip then
                        return string.gsub(first_ip, "^%s*(.-)%s*$", "%1")
                    end
                else
                    local last_ip = nil
                    for ip in string.gmatch(value, "([^,]+)") do
                        last_ip = ip
                    end
                    if last_ip then
                        return string.gsub(last_ip, "^%s*(.-)%s*$", "%1")
                    end
                end
            else
                return value
            end
        end
    end
    
    return waf_utils.get_client_ip()
end

return _M
