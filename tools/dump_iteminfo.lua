-- Usage: lua5.1 dump_iteminfo.lua <iteminfo.lub> <out.json>
-- Loads the compiled iteminfo bytecode, executes it, and serializes the `tbl`
-- table to JSON. Strings are written as raw bytes (client encoding), so a
-- follow-up step must transcode them (see tools/convert_items.py).
local src, out = arg[1], arg[2]
local chunk, err = loadfile(src)
if not chunk then error(err) end

-- The chunk may reference client-side globals; stub them so it runs headless.
setmetatable(_G, { __index = function(_, k) return function() end end })
chunk()
if type(tbl) ~= "table" then error("tbl not found in " .. src) end

local function esc(s)
  s = s:gsub('[%c"\\]', function(c)
    if c == '"' then return '\\"' end
    if c == '\\' then return '\\\\' end
    return string.format("\\u%04x", c:byte())
  end)
  return '"' .. s .. '"'
end

local function ser(v, buf)
  local t = type(v)
  if t == "string" then buf[#buf+1] = esc(v)
  elseif t == "number" then buf[#buf+1] = tostring(v)
  elseif t == "boolean" then buf[#buf+1] = tostring(v)
  elseif t == "table" then
    -- array if keys are 1..n
    local n = #v
    local isArr = n > 0
    if isArr then for k in pairs(v) do if type(k) ~= "number" then isArr = false break end end end
    if isArr then
      buf[#buf+1] = "["
      for i = 1, n do if i > 1 then buf[#buf+1] = "," end ser(v[i], buf) end
      buf[#buf+1] = "]"
    else
      buf[#buf+1] = "{"
      local first = true
      local keys = {}
      for k in pairs(v) do keys[#keys+1] = k end
      table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
      for _, k in ipairs(keys) do
        if not first then buf[#buf+1] = "," end
        first = false
        buf[#buf+1] = esc(tostring(k)) .. ":"
        ser(v[k], buf)
      end
      buf[#buf+1] = "}"
    end
  else buf[#buf+1] = "null" end
end

local buf = {}
ser(tbl, buf)
local f = assert(io.open(out, "wb"))
f:write(table.concat(buf))
f:close()
local count = 0
for _ in pairs(tbl) do count = count + 1 end
io.write(string.format("dumped %d items to %s\n", count, out))
