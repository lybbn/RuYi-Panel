-- =====================================================
-- 如意面板 WAF 规则匹配模块
-- Author: lybbn
-- =====================================================

local _M = {
    _VERSION = '2.0.0'
}

local ngx = ngx
local ngx_re = ngx.re
local waf_utils = require("waf_utils")
local waf_init = require("waf_init")

local function match_patterns(content, patterns, options)
    if not content or content == "" then
        return false, nil
    end
    
    options = options or "joi"
    local decoded_content = waf_utils.url_decode(content)
    decoded_content = string.lower(decoded_content)
    
    for _, pattern in ipairs(patterns) do
        local m = ngx_re.match(decoded_content, pattern, options)
        if m then
            return true, pattern
        end
    end
    
    return false, nil
end

local function match_single_pattern(content, pattern, options)
    if not content or content == "" then
        return false, nil
    end
    
    if not pattern or pattern == "" then
        return false, nil
    end
    
    options = options or "joi"
    local decoded_content = waf_utils.url_decode(content)
    decoded_content = string.lower(decoded_content)
    
    local m = ngx_re.match(decoded_content, pattern, options)
    if m then
        return true, pattern
    end
    
    return false, nil
end

function _M.check_rules_by_category(content, target, category_code)
    local rules = waf_init.get_rules_by_category(category_code)
    
    if not rules or #rules == 0 then
        return false, nil
    end
    
    for _, rule in ipairs(rules) do
        if rule.enabled then
            local targets = rule.targets or {}
            local should_check = false
            
            for _, t in ipairs(targets) do
                if t == target or t == "all" then
                    should_check = true
                    break
                end
            end
            
            if should_check then
                local matched = false
                local pattern = rule.pattern
                
                matched = match_single_pattern(content, pattern)
                
                if matched then
                    return true, {
                        rule_id = rule.rule_id,
                        name = rule.name,
                        pattern = pattern,
                        category = rule.category,
                        severity = rule.severity,
                        is_builtin = rule.is_builtin
                    }
                end
            end
        end
    end
    
    return false, nil
end

function _M.check_sql_injection(content)
    return _M.check_rules_by_category(content, "url", "sql") or
           _M.check_rules_by_category(content, "post", "sql") or
           _M.check_rules_by_category(content, "cookie", "sql")
end

function _M.check_xss(content)
    return _M.check_rules_by_category(content, "url", "xss") or
           _M.check_rules_by_category(content, "post", "xss")
end

function _M.check_command_injection(content)
    return _M.check_rules_by_category(content, "url", "cmd") or
           _M.check_rules_by_category(content, "post", "cmd")
end

function _M.check_path_traversal(content)
    return _M.check_rules_by_category(content, "url", "path")
end

function _M.check_scanner(content)
    return _M.check_rules_by_category(content, "header", "scan")
end

function _M.check_sensitive_file(url)
    return _M.check_rules_by_category(url, "url", "file")
end

function _M.check_bot(content)
    return _M.check_rules_by_category(content, "header", "bot")
end

function _M.check_all_rules(content, target)
    local rules = waf_init.get_rules_by_category()
    
    if not rules or #rules == 0 then
        return false, nil
    end
    
    for _, rule in ipairs(rules) do
        if rule.enabled then
            local targets = rule.targets or {}
            local should_check = false
            
            for _, t in ipairs(targets) do
                if t == target or t == "all" then
                    should_check = true
                    break
                end
            end
            
            if should_check then
                local matched = false
                local pattern = rule.pattern
                
                matched = match_single_pattern(content, pattern)
                
                if matched then
                    return true, {
                        rule_id = rule.rule_id,
                        name = rule.name,
                        pattern = pattern,
                        category = rule.category,
                        severity = rule.severity,
                        is_builtin = rule.is_builtin
                    }
                end
            end
        end
    end
    
    return false, nil
end

function _M.check_request()
    local config = waf_init.global_config
    if not config then
        config = waf_init.load_global_config()
    end
    
    local results = {}
    local blocked = false
    local block_reason = nil
    local matched_rule = nil
    
    local url = waf_utils.get_request_uri()
    local method = waf_utils.get_request_method()
    
    local url_match, url_rule = _M.check_all_rules(url, "url")
    if url_match then
        table.insert(results, { 
            type = url_rule.category or "custom_rule", 
            target = "url", 
            rule = url_rule 
        })
        blocked = true
        block_reason = url_rule.name or "自定义规则"
        matched_rule = url_rule
    end
    
    if not blocked and (method == "POST" or method == "PUT" or method == "PATCH") then
        local body = waf_utils.get_request_body()
        
        local body_match, body_rule = _M.check_all_rules(body, "post")
        if body_match then
            table.insert(results, { 
                type = body_rule.category or "custom_rule", 
                target = "post", 
                rule = body_rule 
            })
            blocked = true
            block_reason = body_rule.name or "自定义规则"
            matched_rule = body_rule
        end
    end
    
    if not blocked then
        local headers = waf_utils.get_headers()
        local header_str = ""
        for k, v in pairs(headers) do
            header_str = header_str .. k .. "=" .. v .. "&"
        end
        
        local header_match, header_rule = _M.check_all_rules(header_str, "header")
        if header_match then
            table.insert(results, { 
                type = header_rule.category or "custom_rule", 
                target = "header", 
                rule = header_rule 
            })
            blocked = true
            block_reason = header_rule.name or "自定义规则"
            matched_rule = header_rule
        end
    end
    
    if not blocked then
        local cookies = waf_utils.get_cookies()
        
        local cookie_match, cookie_rule = _M.check_all_rules(cookies, "cookie")
        if cookie_match then
            table.insert(results, { 
                type = cookie_rule.category or "custom_rule", 
                target = "cookie", 
                rule = cookie_rule 
            })
            blocked = true
            block_reason = cookie_rule.name or "自定义规则"
            matched_rule = cookie_rule
        end
    end
    
    return blocked, block_reason, results, matched_rule
end

return _M
