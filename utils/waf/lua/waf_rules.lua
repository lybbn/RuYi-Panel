-- =====================================================
-- 如意面板 WAF 规则匹配模块
-- Author: lybbn
-- =====================================================

local _M = {
    _VERSION = '3.0.0'
}

local ngx = ngx
local ngx_var = ngx.var
local ngx_req = ngx.req
local ngx_re = ngx.re
local waf_utils = require("waf_utils")
local waf_init = require("waf_init")
local json = require("cjson.safe")

-- 置信度评分阈值：单个 medium 规则 = 1分，high = 3分，critical = 5分
-- 累计达到此阈值才拦截（默认3分，即1个high或3个medium）
local CONFIDENCE_THRESHOLD = 3

-- JSON body 中应跳过检测的长文本字段名（AI聊天、富文本等场景）
-- 这些字段通常包含用户自由输入的长文本，SQL关键词出现在其中是正常的
local JSON_SKIP_FIELDS = {
    ["content"] = true,
    ["prompt"] = true,
    ["message"] = true,
    ["messages"] = true,
    ["text"] = true,
    ["body"] = true,
    ["description"] = true,
    ["remark"] = true,
    ["comment"] = true,
    ["html"] = true,
    ["markdown"] = true,
    ["source_code"] = true,
    ["code"] = true,
    ["query"] = true,
    ["sql"] = true,
    ["answer"] = true,
    ["question"] = true,
    ["input"] = true,
    ["output"] = true,
    ["data"] = true,
    ["context"] = true,
    ["system"] = true,
    ["assistant"] = true,
    ["user"] = true,
    ["role"] = false,
}

-- 长文本字段值超过此长度时跳过检测（字节）
local JSON_VALUE_MAX_LENGTH = 512

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

-- 获取规则的置信度分数
local function get_severity_score(severity)
    local scores = {
        critical = 5,
        high = 3,
        medium = 1,
        low = 1
    }
    return scores[severity] or 1
end

-- 判断请求是否为 JSON API 请求
local function is_json_request()
    local content_type = ngx_var.content_type or ""
    return string.find(string.lower(content_type), "application/json") ~= nil
end

-- 从 JSON body 中提取需要检测的参数值
-- 跳过已知的长文本字段（如 AI 聊天的 content/prompt）
-- 只提取短字符串值用于检测
local function extract_json_values_for_check(body)
    if not body or body == "" then
        return {}
    end
    
    local ok, data = pcall(json.decode, body)
    if not ok or type(data) ~= "table" then
        -- JSON 解析失败，返回空列表，回退到原始 body 检测
        return nil
    end
    
    local values = {}
    
    local function extract_recursive(obj, field_name)
        if type(obj) == "string" then
            -- 跳过已知的长文本字段
            if field_name and JSON_SKIP_FIELDS[field_name] then
                -- 仅当值较短时才检测（可能是参数值而非长文本）
                if #obj <= JSON_VALUE_MAX_LENGTH then
                    table.insert(values, obj)
                end
            else
                table.insert(values, obj)
            end
        elseif type(obj) == "table" then
            for k, v in pairs(obj) do
                local child_name
                if type(k) == "string" then
                    child_name = k
                else
                    child_name = field_name
                end
                extract_recursive(v, child_name)
            end
        elseif type(obj) == "number" or type(obj) == "boolean" then
            -- 数字和布尔值不需要 SQL 注入检测
        end
    end
    
    extract_recursive(data, nil)
    return values
end

-- 对 JSON 请求的 body 进行智能检测
-- 解析 JSON 后只检查短字符串参数值，跳过长文本字段
-- 使用置信度评分，单个 medium 规则命中不直接拦截
local function check_json_body_rules(body, target)
    local values = extract_json_values_for_check(body)
    
    if values == nil then
        -- JSON 解析失败，回退到原始 body 检测
        return nil
    end
    
    if #values == 0 then
        -- 没有需要检测的值（全部是长文本字段被跳过）
        return false, nil, 0
    end
    
    local rules = waf_init.get_rules_by_category()
    if not rules or #rules == 0 then
        return false, nil, 0
    end
    
    local request_url = ngx_var.uri or ""
    local total_score = 0
    local matched_rules = {}
    
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
                -- 检查URL排除列表
                local exclude_urls = rule.exclude_urls
                if exclude_urls and #exclude_urls > 0 then
                    for _, exclude_url in ipairs(exclude_urls) do
                        if waf_utils.str_starts_with(request_url, exclude_url) then
                            should_check = false
                            break
                        end
                    end
                end
            end
            
            if should_check then
                local pattern = rule.pattern
                local rule_matched = false
                
                -- 对每个提取的参数值进行检测
                for _, value in ipairs(values) do
                    local matched = match_single_pattern(value, pattern)
                    if matched then
                        rule_matched = true
                        break
                    end
                end
                
                if rule_matched then
                    local score = get_severity_score(rule.severity)
                    total_score = total_score + score
                    
                    table.insert(matched_rules, {
                        rule_id = rule.rule_id,
                        name = rule.name,
                        pattern = pattern,
                        category = rule.category,
                        severity = rule.severity,
                        is_builtin = rule.is_builtin,
                        score = score
                    })
                    
                    -- high/critical 级别直接拦截（单条规则分数已达到阈值）
                    if score >= CONFIDENCE_THRESHOLD then
                        return true, matched_rules[#matched_rules], total_score
                    end
                end
            end
        end
    end
    
    -- 置信度评分：多个 medium 规则命中且累计分数达到阈值才拦截
    if total_score >= CONFIDENCE_THRESHOLD and #matched_rules > 0 then
        return true, matched_rules[1], total_score
    end
    
    -- 低于阈值：记录但放行（观察模式记录）
    if total_score > 0 and #matched_rules > 0 then
        return false, matched_rules[1], total_score
    end
    
    return false, nil, 0
end

function _M.check_json_body_rules_public(body, target, rule_config, check_mode_enabled_fn)
    local values = extract_json_values_for_check(body)
    
    if values == nil then
        -- JSON 解析失败，回退到原始 body 检测
        return nil
    end
    
    if #values == 0 then
        -- 没有需要检测的值（全部是长文本字段被跳过）
        return false, nil, 0
    end
    
    local rules = waf_init.get_rules_by_category()
    if not rules or #rules == 0 then
        return false, nil, 0
    end
    
    -- 类别到 rule_config 键名的映射
    local category_to_config_key = {
        sql = "sql",
        xss = "xss",
        cmd = "command",
        path = "file_include",
        file = "sensitive_file",
        scan = "scanner",
        bot = "bot",
    }
    
    local request_url = ngx_var.uri or ""
    local total_score = 0
    local matched_rules = {}
    
    for _, rule in ipairs(rules) do
        if rule.enabled then
            -- 如果传入了 check_mode_enabled 函数，检查该类别是否启用
            if check_mode_enabled_fn then
                local config_key = category_to_config_key[rule.category]
                if config_key and not check_mode_enabled_fn(config_key) then
                    goto continue
                end
            end
            
            local targets = rule.targets or {}
            local should_check = false
            
            for _, t in ipairs(targets) do
                if t == target or t == "all" then
                    should_check = true
                    break
                end
            end
            
            if should_check then
                -- 检查URL排除列表
                local exclude_urls = rule.exclude_urls
                if exclude_urls and #exclude_urls > 0 then
                    for _, exclude_url in ipairs(exclude_urls) do
                        if waf_utils.str_starts_with(request_url, exclude_url) then
                            should_check = false
                            break
                        end
                    end
                end
            end
            
            if should_check then
                local pattern = rule.pattern
                local rule_matched = false
                
                -- 对每个提取的参数值进行检测
                for _, value in ipairs(values) do
                    local matched = match_single_pattern(value, pattern)
                    if matched then
                        rule_matched = true
                        break
                    end
                end
                
                if rule_matched then
                    local score = get_severity_score(rule.severity)
                    total_score = total_score + score
                    
                    table.insert(matched_rules, {
                        rule_id = rule.rule_id,
                        name = rule.name,
                        pattern = pattern,
                        category = rule.category,
                        severity = rule.severity,
                        is_builtin = rule.is_builtin,
                        score = score
                    })
                    
                    -- high/critical 级别直接拦截（单条规则分数已达到阈值）
                    if score >= CONFIDENCE_THRESHOLD then
                        return true, matched_rules[#matched_rules], total_score
                    end
                end
            end
            
            ::continue::
        end
    end
    
    -- 置信度评分：多个 medium 规则命中且累计分数达到阈值才拦截
    if total_score >= CONFIDENCE_THRESHOLD and #matched_rules > 0 then
        return true, matched_rules[1], total_score
    end
    
    -- 低于阈值：记录但放行（观察模式记录）
    if total_score > 0 and #matched_rules > 0 then
        return false, matched_rules[1], total_score
    end
    
    return false, nil, 0
end

function _M.check_rules_by_category(content, target, category_code)
    local rules = waf_init.get_rules_by_category(category_code)
    
    if not rules or #rules == 0 then
        return false, nil
    end
    
    local request_url = ngx_var.uri or ""
    
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
                -- 检查URL排除列表
                local exclude_urls = rule.exclude_urls
                if exclude_urls and #exclude_urls > 0 then
                    for _, exclude_url in ipairs(exclude_urls) do
                        if waf_utils.str_starts_with(request_url, exclude_url) then
                            should_check = false
                            break
                        end
                    end
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
    
    local request_url = ngx_var.uri or ""
    
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
                -- 检查URL排除列表
                local exclude_urls = rule.exclude_urls
                if exclude_urls and #exclude_urls > 0 then
                    for _, exclude_url in ipairs(exclude_urls) do
                        if waf_utils.str_starts_with(request_url, exclude_url) then
                            should_check = false
                            break
                        end
                    end
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
    
    -- URL 检测（不受 JSON 智能解析影响）
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
    
    -- POST body 检测
    if not blocked and (method == "POST" or method == "PUT" or method == "PATCH") then
        local body = waf_utils.get_request_body()
        
        if body and body ~= "" then
            -- 判断是否为 JSON 请求，使用智能检测
            if is_json_request() then
                local json_blocked, json_rule, json_score = check_json_body_rules(body, "post")
                
                if json_blocked and json_rule then
                    table.insert(results, { 
                        type = json_rule.category or "custom_rule", 
                        target = "post", 
                        rule = json_rule,
                        confidence_score = json_score
                    })
                    blocked = true
                    block_reason = json_rule.name or "自定义规则"
                    matched_rule = json_rule
                elseif json_score and json_score > 0 and json_rule then
                    -- 低置信度命中，仅记录不拦截
                    table.insert(results, { 
                        type = json_rule.category or "custom_rule", 
                        target = "post", 
                        rule = json_rule,
                        confidence_score = json_score,
                        low_confidence = true
                    })
                end
            else
                -- 非 JSON 请求，使用传统检测
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
        end
    end
    
    -- Header 检测
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
    
    -- Cookie 检测
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
