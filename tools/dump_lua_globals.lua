-- Usage: lua51 dump_lua_globals.lua <file1.lub> [file2.lub ...] <out.json>
-- Runs compiled client Lua table files in order (dependencies first, e.g.
-- accessoryid.lub before accname.lub) and serializes every global table they
-- define (ACCESSORY_IDs, AccNameTable, SPRITE_ROBE_IDs ...) to JSON.
local out = arg[#arg]
local before = {}
for k in pairs(_G) do before[k] = true end
setmetatable(_G, { __index = function(_, k) return function() end end })
for i = 1, #arg - 1 do
  local chunk = assert(loadfile(arg[i]))
  chunk()
end

local function esc(s)
  s = s:gsub('[%c"\\]', function(c)
    if c == '"' then return '\\"' elseif c == '\\' then return '\\\\' end
    return string.format("\\u%04x", c:byte())
  end)
  return '"' .. s .. '"'
end
local function ser(v, buf)
  local t = type(v)
  if t == "string" then buf[#buf+1] = esc(v)
  elseif t == "number" or t == "boolean" then buf[#buf+1] = tostring(v)
  elseif t == "table" then
    buf[#buf+1] = "{"
    local keys, first = {}, true
    for k in pairs(v) do keys[#keys+1] = k end
    table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
    for _, k in ipairs(keys) do
      if type(v[k]) ~= "function" then
        if not first then buf[#buf+1] = "," end
        first = false
        buf[#buf+1] = esc(tostring(k)) .. ":"
        ser(v[k], buf)
      end
    end
    buf[#buf+1] = "}"
  else buf[#buf+1] = "null" end
end

local result, names = {}, {}
for k, v in pairs(_G) do
  if not before[k] and type(v) == "table" then result[k] = v; names[#names+1] = k end
end
local buf = {}
ser(result, buf)
local f = assert(io.open(out, "wb")); f:write(table.concat(buf)); f:close()
table.sort(names)
io.write("dumped globals: " .. table.concat(names, ", ") .. "\n")
