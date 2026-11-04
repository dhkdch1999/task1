/* 인수인계 장부 — 브라우저용 분석 엔진
 * backend/app/{parsers,privacy,analyzer}.py 를 그대로 옮긴 것이다. 규칙을 바꾸면 양쪽을 같이 고친다.
 * 모든 처리는 브라우저 안에서 끝나며 어디에도 전송하지 않는다.
 */
(function (root) {
  "use strict";

  // ------------------------------------------------------------ 공통
  var W = "[\\p{L}\\p{N}_]"; // 파이썬 \b 와 같게 한글도 단어 문자로 본다
  var NB = "(?<!" + W + ")", NA = "(?!" + W + ")";
  // 패턴 안의 "\\b<" 는 앞쪽 경계, "\\b>" 는 뒤쪽 경계를 뜻한다
  function re(src, flags) { return new RegExp(src.split("\\b<").join(NB).split("\\b>").join(NA), (flags || "") + "u"); }

  var KST_DAY = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" });
  function fmt(d) { return d ? KST_DAY.format(d) : null; }
  function dayNum(d) { var p = fmt(d).split("-"); return Date.UTC(+p[0], +p[1] - 1, +p[2]) / 86400000; }
  function median(xs) { var s = xs.slice().sort(function (a, b) { return a - b; }); var n = s.length; return n % 2 ? s[(n - 1) >> 1] : (s[n / 2 - 1] + s[n / 2]) / 2; }
  function uniq(xs) { var seen = new Set(), out = []; xs.forEach(function (x) { if (!seen.has(x)) { seen.add(x); out.push(x); } }); return out; }
  function group(xs, keyFn) { var m = new Map(); xs.forEach(function (x) { var k = keyFn(x); if (!m.has(k)) m.set(k, []); m.get(k).push(x); }); return m; }

  // ------------------------------------------------------------ 개인정보
  var PII = [
    [re("\\b<\\d{6}\\s?-\\s?[1-8]\\d{6}\\b>", "g"), "******-*******"],
    [re("\\b<\\d{4}[- ]\\d{4}[- ]\\d{4}[- ]\\d{4}\\b>", "g"), "****-****-****-****"],
    [re("\\b<01[016789][- .]?\\d{3,4}[- .]?\\d{4}\\b>", "g"), "010-****-****"],
    [re("\\b<0\\d{1,2}[- .]\\d{3,4}[- .]\\d{4}\\b>", "g"), "0**-****-****"],
    [/[\w.+-]+@[\w-]+(\.[\w-]+)+/g, "***@***"],
  ];
  function maskPii(text) { if (!text) return text; var out = text; PII.forEach(function (p) { out = out.replace(p[0], p[1]); }); return out; }

  var FREE_MAIL = ["gmail.com", "naver.com", "daum.net", "hanmail.net", "kakao.com", "nate.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com"];
  var PERSONAL_WORDS = ["택배", "배송", "광고", "할인", "쿠폰", "이벤트", "특가", "동창", "모임", "결혼", "청첩", "개인", "적립", "주문하신", "회원님"];
  var PERSONAL_FOLDERS = ["개인", "personal", "private", "사진", "photo", "다운로드", "downloads"];
  function looksPersonalMail(addr, subjects, ownerDomain) {
    var d = addr.split("@").pop().toLowerCase();
    if (ownerDomain && d === ownerDomain) return false;
    if (FREE_MAIL.indexOf(d) >= 0) return true;
    var j = subjects.join(" ");
    return PERSONAL_WORDS.some(function (w) { return j.indexOf(w) >= 0; });
  }
  function looksPersonalFolder(f) { var l = f.toLowerCase(); return PERSONAL_FOLDERS.some(function (h) { return l.indexOf(h) >= 0; }); }

  function normPath(p) { return p.replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase(); }
  function applyFilters(mails, files, f) {
    var senders = new Set((f.excludeSenders || []).map(function (s) { return s.trim().toLowerCase(); }).filter(Boolean));
    var kws = (f.excludeKeywords || []).map(function (k) { return k.trim().toLowerCase(); }).filter(Boolean);
    var folders = (f.excludeFolders || []).map(normPath).filter(Boolean);
    var km = mails.filter(function (m) {
      if (senders.has(m.senderEmail.toLowerCase())) return false;
      var t = (m.subject + "\n" + m.body).toLowerCase();
      return !kws.some(function (k) { return t.indexOf(k) >= 0; });
    });
    var kf = files.filter(function (x) {
      var p = normPath(x.path);
      if (folders.some(function (fo) { return p === fo || p.indexOf(fo + "/") === 0; })) return false;
      return !kws.some(function (k) { return x.path.toLowerCase().indexOf(k) >= 0; });
    });
    return { mails: km, files: kf, excluded: { mails: mails.length - km.length, files: files.length - kf.length } };
  }

  // ------------------------------------------------------------ MIME 해석
  function bytesFromBinary(s) { var b = new Uint8Array(s.length); for (var i = 0; i < s.length; i++) b[i] = s.charCodeAt(i) & 255; return b; }
  function b64bytes(s) { try { return bytesFromBinary(atob(s.replace(/[^A-Za-z0-9+/=]/g, ""))); } catch (e) { return new Uint8Array(0); } }
  var enc = new TextEncoder();
  function qpBytes(s) {
    s = s.replace(/=\r?\n/g, "");
    var out = [];
    for (var i = 0; i < s.length; i++) {
      var c = s[i];
      if (c === "=" && /^[0-9A-Fa-f]{2}$/.test(s.substr(i + 1, 2))) { out.push(parseInt(s.substr(i + 1, 2), 16)); i += 2; }
      else { enc.encode(c).forEach(function (b) { out.push(b); }); }
    }
    return new Uint8Array(out);
  }
  function decodeBytes(bytes, charset) {
    try { return new TextDecoder((charset || "utf-8").toLowerCase().replace(/^ks_c_5601-1987$/, "euc-kr")).decode(bytes); }
    catch (e) { return new TextDecoder("utf-8").decode(bytes); }
  }
  function decodeWords(s) {
    if (!s) return "";
    return s.replace(/(=\?[^?]+\?[bBqQ]\?[^?]*\?=)\s+(?==\?)/g, "$1").replace(/=\?([^?*]+)(?:\*[^?]*)?\?([bBqQ])\?([^?]*)\?=/g, function (_, cs, e, t) {
      return decodeBytes(e.toUpperCase() === "B" ? b64bytes(t) : qpBytes(t.replace(/_/g, " ")), cs);
    });
  }
  function splitOutside(s, sep) {
    var out = [], cur = "", q = false, ang = 0;
    for (var i = 0; i < s.length; i++) {
      var c = s[i];
      if (c === '"' && s[i - 1] !== "\\") q = !q;
      if (!q && c === "<") ang++;
      if (!q && c === ">") ang = Math.max(0, ang - 1);
      if (c === sep && !q && !ang) { out.push(cur); cur = ""; } else cur += c;
    }
    out.push(cur);
    return out;
  }
  function parseHeaders(text) {
    var h = {}, lines = text.split(/\r?\n/), cur = null;
    lines.forEach(function (ln) {
      if (/^[ \t]/.test(ln) && cur) { h[cur] += " " + ln.trim(); return; }
      var i = ln.indexOf(":");
      if (i <= 0) return;
      var name = ln.slice(0, i).trim().toLowerCase();
      if (name in h) { cur = null; return; } // 같은 머리글이 또 나오면 첫 번째만 쓴다
      cur = name;
      h[cur] = ln.slice(i + 1).trim();
    });
    return h;
  }
  function decode2231(v) {
    var m = /^([^']*)'[^']*'(.*)$/.exec(v);
    var cs = m ? m[1] : "utf-8", body = m ? m[2] : v;
    var bytes = [];
    for (var i = 0; i < body.length; i++) {
      if (body[i] === "%" && /^[0-9A-Fa-f]{2}$/.test(body.substr(i + 1, 2))) { bytes.push(parseInt(body.substr(i + 1, 2), 16)); i += 2; }
      else enc.encode(body[i]).forEach(function (b) { bytes.push(b); });
    }
    return decodeBytes(new Uint8Array(bytes), cs || "utf-8");
  }
  function parseParams(v) {
    var parts = splitOutside(v || "", ";"), main = (parts.shift() || "").trim().toLowerCase(), raw = {};
    parts.forEach(function (p) {
      var i = p.indexOf("=");
      if (i < 0) return;
      var k = p.slice(0, i).trim().toLowerCase(), val = p.slice(i + 1).trim();
      if (val[0] === '"') val = val.slice(1, -1).replace(/\\(.)/g, "$1");
      raw[k] = val;
    });
    var params = {};
    Object.keys(raw).forEach(function (k) {
      var m = /^([^*]+)\*(\d+)?(\*)?$/.exec(k);
      if (!m) { if (!(k in params)) params[k] = decodeWords(raw[k]); return; }
      var base = m[1];
      if (m[2] === undefined) { params[base] = decode2231(raw[k]); return; }
      if (params["__done_" + base]) return;
      var segs = Object.keys(raw).map(function (kk) { var mm = /^([^*]+)\*(\d+)(\*)?$/.exec(kk); return mm && mm[1] === base ? { n: +mm[2], k: kk, e: !!mm[3] } : null; })
        .filter(Boolean).sort(function (a, b) { return a.n - b.n; });
      var joined = segs.map(function (s) { return raw[s.k]; }).join("");
      params[base] = segs[0] && segs[0].e ? decode2231(joined) : joined;
      params["__done_" + base] = true;
    });
    return { value: main, params: params };
  }
  function decodeBody(body, cte, charset) {
    cte = (cte || "").toLowerCase();
    if (cte === "base64") return decodeBytes(b64bytes(body), charset);
    if (cte === "quoted-printable") return decodeBytes(qpBytes(body), charset);
    return body;
  }
  function parseEntity(raw, acc) {
    var m = /\r?\n\r?\n/.exec(raw);
    var head = m ? raw.slice(0, m.index) : raw, body = m ? raw.slice(m.index + m[0].length) : "";
    var h = parseHeaders(head);
    var ct = parseParams(h["content-type"] || "text/plain");
    var cd = parseParams(h["content-disposition"] || "");
    var fname = cd.params.filename || ct.params.name;
    if (ct.value.indexOf("multipart/") === 0 && ct.params.boundary) {
      var b = "--" + ct.params.boundary;
      var chunks = body.split(new RegExp("^" + b.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?:--)?[ \\t]*$", "m"));
      chunks.slice(1, -1).forEach(function (c) { parseEntity(c.replace(/^\r?\n/, ""), acc); });
      if (chunks.length === 2) parseEntity(chunks[1].replace(/^\r?\n/, ""), acc);
    } else if (cd.value === "attachment" || (fname && ct.value.indexOf("text/") !== 0)) {
      if (fname) acc.attachments.push(fname);
    } else if (ct.value === "text/plain" && acc.plain === null) {
      acc.plain = decodeBody(body, h["content-transfer-encoding"], ct.params.charset);
    } else if (ct.value === "text/html" && acc.html === null) {
      acc.html = decodeBody(body, h["content-transfer-encoding"], ct.params.charset);
    } else if (ct.value === "message/rfc822") {
      parseEntity(body, acc);
    }
    return h;
  }
  function parseAddrs(v) {
    if (!v) return [];
    return splitOutside(v, ",").map(function (tok) {
      tok = tok.trim();
      if (!tok) return null;
      var m = /^(.*)<([^>]+)>\s*$/.exec(tok), name, addr;
      if (m) { name = decodeWords(m[1]).trim().replace(/^"|"$/g, "").trim(); addr = m[2].trim().toLowerCase(); }
      else { addr = tok.replace(/^"|"$/g, "").trim().toLowerCase(); name = ""; }
      if (addr.indexOf("@") < 0) return null;
      return [name || addr.split("@")[0], addr];
    }).filter(Boolean);
  }
  function parseDate(v) {
    if (!v) return null;
    v = String(v).trim();
    if (!v) return null;
    var m = /(\d{4})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})\.?(?:[ T]+(오전|오후|AM|PM)?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?)?/i.exec(v);
    if (m && !/[+-]\d{2}:?\d{2}$|Z$/.test(v)) {
      var hour = m[5] ? +m[5] : 0, ap = (m[4] || m[8] || "").toUpperCase();
      if ((ap === "오후" || ap === "PM") && hour < 12) hour += 12;
      if ((ap === "오전" || ap === "AM") && hour === 12) hour = 0;
      var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], hour - 9, +(m[6] || 0), +(m[7] || 0)));
      return isNaN(d) ? null : d;
    }
    var t = Date.parse(v);
    return isNaN(t) ? null : new Date(t);
  }
  function messageToMail(raw, fallbackId) {
    var acc = { plain: null, html: null, attachments: [] };
    var h = parseEntity(raw, acc);
    var from = parseAddrs(h.from);
    if (!from.length) return null;
    var body = acc.plain !== null ? acc.plain : acc.html !== null ? acc.html.replace(/<[^>]+>/g, " ") : "";
    return {
      id: (h["message-id"] || fallbackId).replace(/[<>\s]/g, ""),
      senderName: from[0][0], senderEmail: from[0][1],
      to: parseAddrs(h.to), cc: parseAddrs(h.cc),
      date: parseDate(h.date), subject: decodeWords(h.subject || "").trim(),
      body: body.replace(/[ \t]+/g, " ").trim(), attachments: acc.attachments,
    };
  }
  function parseMbox(text) {
    var lines = text.split(/\r?\n/), msgs = [], cur = null;
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].indexOf("From ") === 0 && (i === 0 || lines[i - 1] === "")) { if (cur) msgs.push(cur); cur = []; continue; }
      if (cur) cur.push(lines[i].replace(/^>(>*From )/, "$1"));
    }
    if (cur) msgs.push(cur);
    return msgs.map(function (ls, i) { return messageToMail(ls.join("\n"), "mbox-" + i); }).filter(Boolean);
  }

  // ------------------------------------------------------------ CSV
  function parseCsv(text) {
    text = text.replace(/^﻿/, "");
    var rows = [], row = [], cell = "", q = false;
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; }
        else cell += c;
      } else if (c === '"') q = true;
      else if (c === ",") { row.push(cell); cell = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
      else cell += c;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    return rows.filter(function (r) { return r.some(function (x) { return x.trim(); }); });
  }
  function matchHeaders(headers, spec) {
    var low = headers.map(function (h) { return h.trim().toLowerCase(); }), found = {}, used = new Set();
    Object.keys(spec).forEach(function (key) {
      for (var i = 0; i < spec[key].length; i++) {
        var idx = low.indexOf(spec[key][i]);
        if (idx >= 0 && !used.has(idx)) { found[key] = idx; used.add(idx); break; }
      }
    });
    return found;
  }
  var MAIL_COLS = {
    subject: ["subject", "제목"],
    from_addr: ["from: (address)", "보낸 사람: (주소)", "from address", "보낸사람주소", "sender email"],
    from_name: ["from: (name)", "보낸 사람: (이름)", "from name", "보낸사람"],
    from: ["from", "보낸 사람", "sender"],
    to: ["to: (address)", "받는 사람: (주소)", "to", "받는 사람", "받는사람"],
    cc: ["cc: (address)", "참조: (주소)", "cc", "참조"],
    date: ["date", "날짜", "보낸 날짜", "받은 날짜", "sent", "received"],
    body: ["body", "본문", "내용"],
    attachments: ["attachments", "첨부", "첨부파일"],
  };
  function parseMailCsv(text) {
    var rows = parseCsv(text);
    if (!rows.length) return [];
    var cols = matchHeaders(rows[0], MAIL_COLS), out = [];
    rows.slice(1).forEach(function (r, i) {
      function g(k) { return k in cols ? (r[cols[k]] || "").trim() : ""; }
      var s = parseAddrs((g("from_addr") || g("from")).replace(/;/g, ","));
      if (!s.length) return;
      out.push({
        id: "csv-" + i, senderName: g("from_name") || s[0][0], senderEmail: s[0][1],
        to: parseAddrs(g("to").replace(/;/g, ",")), cc: parseAddrs(g("cc").replace(/;/g, ",")),
        date: parseDate(g("date")), subject: g("subject"), body: g("body"),
        attachments: g("attachments").split(/[;|]/).map(function (a) { return a.trim(); }).filter(Boolean),
      });
    });
    return out;
  }
  function parseMailSource(name, content) {
    var l = name.toLowerCase();
    if (/\.csv$/.test(l)) return parseMailCsv(content);
    if (/\.mbox$/.test(l) || content.indexOf("From ") === 0) return parseMbox(content);
    var m = messageToMail(content, name);
    return m ? [m] : [];
  }
  var FILE_COLS = {
    path: ["path", "fullname", "경로", "전체 경로", "파일 경로", "file"],
    modified: ["modified", "lastwritetime", "수정일", "수정한 날짜", "수정 날짜", "date"],
    size: ["size", "length", "크기"],
  };
  function normalizePath(p) { return p.trim().replace(/^"|"$/g, "").replace(/\\/g, "/"); }
  function parseFileList(name, content) {
    var text = content.replace(/^﻿/, ""), first = (text.split(/\r?\n/)[0] || "").toLowerCase();
    if (first.indexOf(",") >= 0 && /path|fullname|경로|file/.test(first)) {
      var rows = parseCsv(text), cols = matchHeaders(rows[0], FILE_COLS);
      return rows.slice(1).map(function (r) {
        var p = normalizePath(r[cols.path] || "");
        var sz = ((r[cols.size] || "") + "").replace(/,/g, "").trim();
        return p ? { path: p, modified: parseDate(r[cols.modified]), size: /^\d+$/.test(sz) ? +sz : null } : null;
      }).filter(Boolean);
    }
    return text.split(/\r?\n/).map(normalizePath).filter(function (p) { return p && p.split("/").pop().indexOf(".") >= 0; })
      .map(function (p) { return { path: p, modified: null, size: null }; });
  }
  function fileName(p) { return p.split("/").pop(); }
  function fileFolder(p) { var i = p.lastIndexOf("/"); return i >= 0 ? p.slice(0, i) : ""; }

  // ------------------------------------------------------------ 정규화
  var PREFIX = /^\s*(?:(?:re|fw|fwd|회신|답장|전달)\s*[:：]\s*|\[(?:re|fw|fwd)\]\s*)/i;
  var TAG = /\[[^\]]{1,10}\]|\([^)]{0,10}(?:주차|월|분기)[^)]{0,6}\)/g;
  var DATE_TOKENS = [
    re("\\d{4}\\s*[년._\\-/]\\s*\\d{1,2}\\s*[월._\\-/]?\\s*(?:\\d{1,2}\\s*일?)?", "g"),
    re("\\d{4}\\s*[_\\-]?\\s*(?:w|wk)\\s*\\d{1,2}", "gi"),
    re("\\d{4}\\s*[_\\-]?\\s*q[1-4]", "gi"),
    re("\\d{1,2}\\s*월\\s*(?:\\d{1,2}\\s*주차|\\d{1,2}\\s*일)?", "g"),
    re("\\d{1,2}\\s*주차", "g"),
    re("[1-4]\\s*분기|q[1-4]\\b>", "gi"),
    re("\\b<\\d{1,2}/\\d{1,2}\\b>", "g"),
    re("\\b<(?:19|20)\\d{2}(?:\\d{4})?\\b>", "g"),
  ];
  var VERSION = /(?:[_\-\s(]*)(?:v\d+(?:\.\d+)?|ver\s?\d+|최종(?:본)?|수정(?:본)?|final|draft|초안|\d차)\)?/gi;
  var VERSION_TEST = /(?:v\d+(?:\.\d+)?|ver\s?\d+|최종(?:본)?|수정(?:본)?|final|draft|초안|\d차)/i;

  function stripPrefixes(s) { var prev = null; while (prev !== s) { prev = s; s = s.replace(PREFIX, ""); } return s.trim(); }
  function stripDates(t) { DATE_TOKENS.forEach(function (r) { t = t.replace(r, " "); }); return t; }
  function cleanTitle(subject) {
    var s = stripPrefixes(subject).replace(TAG, " ");
    // 밑줄은 띄어쓰기로, 하이픈은 'HX-500'처럼 글자 사이가 아닐 때만 띄어쓰기로 바꾼다
    s = stripDates(s).replace(/_+|(?<![0-9A-Za-z])-+|-+(?![0-9A-Za-z])/g, " ").replace(/\(\s*\)|\[\s*\]/g, " ")
      .replace(/\s+/g, " ").replace(/^[ .,:\-]+|[ .,:\-]+$/g, "");
    s = s.replace(/\s*(?:건|송부|공유드립니다|보내드립니다)$/, "").trim();
    return s || stripPrefixes(subject);
  }
  function compact(t) { return t.toLowerCase().replace(/[^0-9a-z가-힣]/g, ""); }
  function topicKey(s) { return compact(cleanTitle(s)); }
  function threadKey(s) { return stripPrefixes(s).replace(/\s+/g, " ").trim().toLowerCase(); }
  function stem(n) { var i = n.lastIndexOf("."); return i > 0 ? n.slice(0, i) : n; }
  function fileBase(n) { return compact(stripDates(stem(n)).replace(VERSION, " ")); }
  function fileDisplayBase(n) { var s = stem(n); var t = stripDates(s).replace(VERSION, " ").replace(/[_\-\s]+/g, " ").trim(); return t || s; }
  function folderLabel(f) { var leaf = f.split("/").pop(); return leaf.replace(/^\d+[_.\-\s]*/, "").trim() || leaf; }
  function splitName(n) { var m = /^\s*(.+?)\s*[\(\[](.+?)[\)\]]\s*$/.exec(n); return m ? [m[1], m[2]] : [n.trim(), null]; }

  function cycleFromIntervals(dates) {
    var days = uniq(dates.map(dayNum)).sort(function (a, b) { return a - b; });
    if (days.length < 2) return "비정기";
    var gaps = days.slice(1).map(function (d, i) { return d - days[i]; });
    if (median(gaps) > 2) {
      var cl = [days[0]];
      days.slice(1).forEach(function (d) { if (d - cl[cl.length - 1] > 3) cl.push(d); });
      if (cl.length < 2) return "비정기";
      gaps = cl.slice(1).map(function (d, i) { return d - cl[i]; });
    }
    var med = median(gaps), spread = Math.max.apply(null, gaps) - Math.min.apply(null, gaps);
    if (med <= 2) return "매일";
    if (med >= 5 && med <= 9 && spread <= 10) return "매주";
    if (med >= 24 && med <= 38 && spread <= 25) return "매월";
    if (med >= 75 && med <= 105) return "분기";
    return "비정기";
  }
  function count(rx, s) { return (s.match(rx) || []).length; }
  function cycleFromFileTokens(names) {
    var j = names.join(" ");
    if (count(/(?:w|wk)\s*\d{1,2}|\d{1,2}\s*주차/gi, j) >= 2) return "매주";
    if (count(/q[1-4]|[1-4]\s*분기/gi, j) >= 2) return "분기";
    if (count(/\d{4}\s*[년._\-]\s*\d{1,2}(?!\d)|\d{1,2}\s*월/g, j) >= 2) return "매월";
    return null;
  }
  var CATS = [
    ["고객 대응", ["고객", "채터링", "클레임", "a/s", "현장", "방문", "가공"]],
    ["품질·불량", ["불량", "필드", "알람", "결함", "회귀", "품질"]],
    ["개발·릴리스", ["릴리스", "배포", "펌웨어", "빌드", "버전", "jenkins"]],
    ["인증·안전", ["인증", "기능안전", "fmea", "iec", "안전"]],
    ["세무", ["세무", "부가세", "원천세", "세금", "신고"]],
    ["정산·회계", ["정산", "비용", "법인카드", "경비", "회계", "결산", "증빙"]],
    ["보고", ["보고", "주간", "월간", "실적", "회의록"]],
    ["구매·발주", ["발주", "구매", "견적", "사무용품", "주문서"]],
    ["계약·거래처", ["계약", "갱신", "거래처", "협력사", "물류", "공급사", "호환성"]],
    ["IT·장비", ["노트북", "장비", "계정", "pc", "세팅", "it"]],
    ["인사·총무", ["입사", "퇴사", "교육", "채용", "총무", "복리후생"]],
    ["프로젝트", ["프로젝트", "이전", "레이아웃", "구축", "도입", "전환", "시제품"]],
  ];
  var AUTOMATED = /^(?:no-?reply|donotreply|do-not-reply|jenkins|ci|build|builds|alert|alerts|notification|notifications|notify|system|mailer-daemon|postmaster|monitor|bot)(?:[._+-][^@]*)?@/i;
  function isAutomated(addr) { return AUTOMATED.test(addr); } // 빌드 서버·알림처럼 답장할 대상이 아닌 발신자
  function categorize(text) {
    var low = text.toLowerCase(), best = "기타", score = 0;
    CATS.forEach(function (c) { var s = c[1].filter(function (w) { return low.indexOf(w) >= 0; }).length; if (s > score) { best = c[0]; score = s; } });
    return best;
  }
  var QUOTE_SPLIT = /-{2,}\s*(?:original message|원본 메시지)|^\s*>|^\s*20\d\d.*(?:wrote|작성):/im;
  var SIGN = /^\s*\S{1,10}\s*(?:드림|올림|배상)\.?\s*$/gm;
  function snippet(body, limit) {
    limit = limit || 90;
    var t = body.split(QUOTE_SPLIT)[0].replace(SIGN, "").replace(/\s+/g, " ").trim();
    return maskPii(t.slice(0, limit) + (t.length > limit ? "…" : ""));
  }

  // ------------------------------------------------------------ 분석
  var RECENT_DAYS = 14;
  function ev(kind, label, date) { return { kind: kind, label: label, date: date || null }; }

  function detectOwner(mails, ownerEmail) {
    if (ownerEmail) return ownerEmail.trim().toLowerCase();
    var c = new Map();
    mails.forEach(function (m) { c.set(m.senderEmail, (c.get(m.senderEmail) || 0) + 1); m.to.forEach(function (t) { c.set(t[1], (c.get(t[1]) || 0) + 1); }); });
    var best = null, n = -1;
    c.forEach(function (v, k) { if (v > n) { n = v; best = k; } });
    return best;
  }

  function analyze(mails, files, ownerEmail, baseOverride) {
    var owner = detectOwner(mails, ownerEmail);
    var ownerDomain = owner ? owner.split("@").pop() : null;
    var all = mails.filter(function (m) { return m.date; }).map(function (m) { return m.date; })
      .concat(files.filter(function (f) { return f.modified; }).map(function (f) { return f.modified; }));
    var base = baseOverride || (all.length ? new Date(Math.max.apply(null, all)) : new Date());
    var recentFrom = new Date(base.getTime() - RECENT_DAYS * 86400000);
    var FAR = new Date(0);
    function t(d) { return (d || FAR).getTime(); }

    // 연락처
    var people = new Map();
    function touch(name, addr) {
      if (!addr || addr === owner) return;
      var sn = splitName(name);
      if (!people.has(addr)) people.set(addr, { name: sn[0], email: addr, org: sn[1], count: 0, internal: !!(ownerDomain && addr.slice(-ownerDomain.length - 1) === "@" + ownerDomain) });
      var p = people.get(addr);
      p.count++;
      if (sn[1] && !p.org) p.org = sn[1];
    }
    mails.forEach(function (m) {
      if (m.senderEmail === owner) m.to.concat(m.cc).forEach(function (x) { touch(x[0], x[1]); });
      else touch(m.senderName, m.senderEmail);
    });
    people.forEach(function (p) { if (!p.org) p.org = p.internal ? "사내" : p.email.split("@").pop(); });
    function participants(m) { return [[m.senderName, m.senderEmail]].concat(m.to, m.cc); }
    function peopleOf(group, limit) {
      var c = new Map();
      group.forEach(function (m) { participants(m).forEach(function (x) { if (people.has(x[1])) c.set(x[1], (c.get(x[1]) || 0) + 1); }); });
      return Array.from(c.entries()).sort(function (a, b) { return b[1] - a[1]; }).slice(0, limit || 4)
        .map(function (e) { var p = people.get(e[0]); return { name: p.name, email: e[0], org: p.org }; });
    }

    var topics = group(mails.filter(function (m) { return topicKey(m.subject); }), function (m) { return topicKey(m.subject); });

    var fileGroups = new Map(); // key "folder\u0000base"
    files.forEach(function (f) {
      var b = fileBase(fileName(f.path));
      if (!b) return;
      var k = fileFolder(f.path) + "\u0000" + b;
      if (!fileGroups.has(k)) fileGroups.set(k, []);
      fileGroups.get(k).push(f);
    });
    var filesByBase = new Map();
    fileGroups.forEach(function (_, k) { var b = k.split("\u0000")[1]; if (!filesByBase.has(b)) filesByBase.set(b, []); filesByBase.get(b).push(k); });

    var usedGroups = new Set(), usedFiles = new Set(), cards = [];
    function matchAttachments(group) {
      var found = [];
      group.forEach(function (m) { m.attachments.forEach(function (a) { var ab = fileBase(a); (filesByBase.get(ab) || []).forEach(function (k) { if (ab && found.indexOf(k) < 0) found.push(k); }); }); });
      return found;
    }
    var allFolders = uniq(files.map(function (f) { return fileFolder(f.path); }));
    // 제목에 폴더 이름이 들어 있거나, 상대방 소속(예: '세진모션')이 폴더 이름과 같으면 연결한다
    function matchFolders(subject, grp) {
      var sc = compact(cleanTitle(subject)), orgs = new Set();
      (grp || []).forEach(function (m) { participants(m).forEach(function (x) { var o = splitName(x[0])[1]; if (x[1] !== owner && o) orgs.add(compact(o)); }); });
      return allFolders.filter(function (fo) { var l = compact(folderLabel(fo)); return l.length >= 3 && (sc.indexOf(l) >= 0 || orgs.has(l)); });
    }
    function sender(m) { return splitName(m.senderName)[0]; }

    // 1) 메일 기반 반복 업무
    var recurring = new Set();
    topics.forEach(function (group, k) {
      var dated = group.filter(function (m) { return m.date; });
      var starts = dated.filter(function (m) { return stripPrefixes(m.subject) === m.subject.trim(); });
      var distinct = uniq(starts.map(function (m) { return fmt(m.date); }));
      var matched = matchAttachments(group);
      var fileCount = matched.reduce(function (n, g) { return n + fileGroups.get(g).length; }, 0);
      if (distinct.length < 3 && !(distinct.length >= 2 && fileCount >= 3)) return;
      var cycle = cycleFromIntervals(starts.map(function (m) { return m.date; }));
      if (cycle === "비정기" && matched.length) cycle = cycleFromFileTokens([].concat.apply([], matched.map(function (g) { return fileGroups.get(g).map(function (f) { return fileName(f.path); }); }))) || cycle;
      if (cycle === "비정기") return;
      recurring.add(k);
      var latest = dated.reduce(function (a, b) { return t(b.date) > t(a.date) ? b : a; });
      var needsReply = latest.date >= recentFrom && latest.senderEmail !== owner && !isAutomated(latest.senderEmail);
      var inbound = group.filter(function (m) { return m.senderEmail !== owner; });
      var allAuto = inbound.length > 0 && inbound.every(function (m) { return isAutomated(m.senderEmail); });
      var sent = group.filter(function (m) { return m.senderEmail === owner; });
      var dir = sent.length >= group.length / 2 ? "보내는" : "받는";
      var cp = peopleOf(dir === "보내는" ? sent : group, 3);
      var who = cp.map(function (p) { return p.name; }).join(", ") || "관련 담당자";
      var rel = uniq([].concat.apply([], matched.map(function (g) { return fileGroups.get(g).map(function (f) { return f.path; }); }))).sort().reverse();
      matched.forEach(function (g) { usedGroups.add(g); fileGroups.get(g).forEach(function (f) { usedFiles.add(f.path); }); });
      var desc = allAuto
        ? cycle + " 자동 알림 메일이 옵니다(보낸 곳: " + sender(inbound[0]) + "). 알림을 확인하고 필요한 조치를 하는 업무로 보입니다."
        : cycle + " " + who + "에게 " + (dir === "보내는" ? "메일을 보내는" : "메일을 받아 처리하는") + " 업무로 보입니다.";
      if (rel.length) desc += " 관련 파일 " + rel.length + "개가 같은 이름 규칙으로 쌓여 있습니다.";
      if (needsReply) {
        var lt = snippet(latest.body);
        desc += " 최근 " + sender(latest) + "님이 보낸 메일에 아직 답장하지 않았습니다.";
        if (lt) desc += ' 마지막 내용: "' + lt + '"';
      }
      var evs = dated.slice().sort(function (a, b) { return t(b.date) - t(a.date); }).map(function (m) { return ev("mail", stripPrefixes(m.subject) + " — " + sender(m), fmt(m.date)); })
        .concat(rel.slice(0, 2).map(function (p) { return ev("file", p + " (첨부파일과 같은 이름)"); }));
      var score = 1 + (distinct.length >= 3 ? 1 : 0) + (rel.length ? 1 : 0);
      cards.push({ title: cleanTitle(latest.subject), description: desc, cycle: cycle, status: "정기",
        category: categorize(group.map(function (m) { return m.subject; }).join(" ") + " " + latest.body.slice(0, 200)),
        related_files: rel.slice(0, 6), related_people: cp, evidence: evs, evidence_total: group.length + rel.length,
        confidence: ["low", "low", "medium", "high"][score], needs_reply: needsReply, caution: "", _sort: latest.date });
    });

    // 2) 스레드
    var threads = group(mails.filter(function (m) { return !recurring.has(topicKey(m.subject)); }), function (m) { return threadKey(m.subject); });
    threads.forEach(function (group) {
      var dated = group.filter(function (m) { return m.date; }).sort(function (a, b) { return t(a.date) - t(b.date); });
      if (group.length < 2 || !dated.length) return;
      var last = dated[dated.length - 1];
      var isRecent = last.date >= recentFrom, needsReply = isRecent && last.senderEmail !== owner && !isAutomated(last.senderEmail);
      var folders = matchFolders(last.subject, group);
      var ff = files.filter(function (f) { return folders.indexOf(fileFolder(f.path)) >= 0; })
        .sort(function (a, b) { return (b.modified ? b.modified.getTime() : -1e15) - (a.modified ? a.modified.getTime() : -1e15); });
      var matched = matchAttachments(group);
      var rel = ff.map(function (f) { return f.path; });
      matched.forEach(function (g) { fileGroups.get(g).forEach(function (f) { rel.push(f.path); }); });
      rel = uniq(rel);
      rel.forEach(function (p) { usedFiles.add(p); });
      fileGroups.forEach(function (_, k) { if (folders.indexOf(k.split("\u0000")[0]) >= 0) usedGroups.add(k); });
      var recentFiles = ff.filter(function (f) { return f.modified && f.modified >= recentFrom; });
      var status = isRecent || recentFiles.length ? "진행 중" : "완료";
      var lt = snippet(last.body);
      var desc = "메일 " + group.length + "건이 오간 업무입니다. 마지막 메일은 " + fmt(last.date) + "에 " + sender(last) + "님이 보냈습니다.";
      if (needsReply) desc += " 아직 답장하지 않은 것으로 보입니다.";
      if (lt) desc += ' 마지막 내용: "' + lt + '"';
      if (recentFiles.length) desc += " 관련 폴더에서 최근 " + RECENT_DAYS + "일 안에 수정된 파일이 " + recentFiles.length + "개 있습니다.";
      var evs = dated.slice().reverse().map(function (m) { return ev("mail", stripPrefixes(m.subject) + " — " + sender(m), fmt(m.date)); })
        .concat(recentFiles.slice(0, 3).map(function (f) { return ev("file", f.path + " (최근 수정)", fmt(f.modified)); }));
      var score = 1 + (group.length >= 3 ? 1 : 0) + (rel.length ? 1 : 0);
      cards.push({ title: cleanTitle(last.subject), description: desc, cycle: "비정기", status: status,
        category: categorize(group.map(function (m) { return m.subject; }).join(" ") + " " + folders.join(" ")),
        related_files: rel.slice(0, 6), related_people: peopleOf(group, 4), evidence: evs, evidence_total: group.length + rel.length,
        confidence: ["low", "low", "medium", "high"][score], needs_reply: needsReply, caution: "", _sort: last.date });
    });

    // 3) 파일만으로 보이는 반복 산출물
    var templates = [];
    fileGroups.forEach(function (group, key) {
      if (usedGroups.has(key)) return;
      var folder = key.split("\u0000")[0];
      if (/양식|템플릿|template|서식/i.test(folder)) { templates = templates.concat(group); return; }
      var cyc = group.length >= 3 ? cycleFromFileTokens(group.map(function (f) { return fileName(f.path); })) : null;
      if (!cyc) return;
      usedGroups.add(key);
      group.forEach(function (f) { usedFiles.add(f.path); });
      var latest = group.reduce(function (a, b) { return t(b.modified) > t(a.modified) ? b : a; });
      var disp = fileDisplayBase(fileName(latest.path));
      var head = compact(disp).slice(0, 4), host = null;
      var same = cards.filter(function (c) { return c.cycle === cyc && c.status === "정기"; });
      for (var i = 0; i < same.length && !host; i++) if (head.length >= 3 && compact(same[i].title).indexOf(head) >= 0) host = same[i];
      for (var j = 0; j < same.length && !host; j++) {
        var cf = uniq(same[j].related_files.map(fileFolder));
        if (cf.some(function (c) { return folder === c || folder.indexOf(c + "/") === 0; })) host = same[j];
      }
      if (host) {
        var newest = group.map(function (f) { return f.path; }).sort().reverse();
        host.related_files = host.related_files.concat(newest.slice(0, 2));
        host.evidence.push(ev("file", "'" + disp + "' 파일도 " + cyc + " 같은 폴더에 함께 쌓임 (" + group.length + "개)", fmt(latest.modified)));
        host.evidence_total += group.length;
        return;
      }
      cards.push({ title: disp, cycle: cyc, status: "정기", category: categorize(disp + " " + folder),
        description: "'" + folderLabel(folder) + "' 폴더에 " + cyc + " 단위로 '" + disp + "' 파일이 만들어지고 있습니다. 메일로 보낸 흔적은 찾지 못했으니 누구에게 전달하는지 직접 적어 주세요.",
        related_files: group.map(function (f) { return f.path; }).sort().reverse().slice(0, 6), related_people: [],
        evidence: group.slice().sort(function (a, b) { return fileName(b.path) < fileName(a.path) ? -1 : 1; }).map(function (f) { return ev("file", f.path, fmt(f.modified)); }),
        evidence_total: group.length, confidence: group.length >= 4 ? "medium" : "low", needs_reply: false, caution: "", _sort: latest.modified });
    });

    // 4) 최근 작업 폴더
    var tplSet = new Set(templates.map(function (f) { return f.path; }));
    var recentBy = group(files.filter(function (f) { return !usedFiles.has(f.path) && !tplSet.has(f.path) && f.modified && f.modified >= recentFrom; }), function (f) { return fileFolder(f.path); });
    recentBy.forEach(function (group, folder) {
      if (group.length < 2) return;
      group.forEach(function (f) { usedFiles.add(f.path); });
      var label = folderLabel(folder);
      var sorted = group.slice().sort(function (a, b) { return t(b.modified) - t(a.modified); });
      cards.push({ title: label + " 폴더 작업", cycle: "비정기", status: "진행 중", category: categorize(folder),
        description: "최근 " + RECENT_DAYS + "일 안에 '" + label + "' 폴더의 파일 " + group.length + "개가 수정되었습니다. 관련 메일은 찾지 못했습니다. 어떤 업무인지 설명을 보완해 주세요.",
        related_files: sorted.map(function (f) { return f.path; }).slice(0, 6), related_people: [],
        evidence: group.map(function (f) { return ev("file", f.path + " (최근 수정)", fmt(f.modified)); }),
        evidence_total: group.length, confidence: "low", needs_reply: false, caution: "", _sort: sorted[0].modified });
    });

    // 5) 버전 문서, 양식
    var versioned = group(files.filter(function (f) { return VERSION_TEST.test(stem(fileName(f.path))); }), function (f) { return fileFolder(f.path) + "/" + fileBase(fileName(f.path)); });
    versioned.forEach(function (vf) {
      if (vf.length < 2) return;
      var paths = new Set(vf.map(function (f) { return f.path; }));
      for (var i = 0; i < cards.length; i++) {
        var c = cards[i];
        if (c.related_files.some(function (p) { return paths.has(p); })) {
          var latest = vf.reduce(function (a, b) { return t(b.modified) > t(a.modified) ? b : a; });
          c.evidence.push(ev("file", fileDisplayBase(fileName(latest.path)) + " — " + vf.length + "개 버전으로 수정됨 (핵심 문서)", fmt(latest.modified)));
          if (c.related_files[0] !== latest.path) c.related_files = [latest.path].concat(c.related_files.filter(function (p) { return p !== latest.path; }));
          break;
        }
      }
    });
    var leftover = [];
    templates.forEach(function (tp) {
      var tb = compact(fileDisplayBase(fileName(tp.path))), done = false;
      for (var i = 0; i < cards.length && !done; i++) {
        var ct = compact(cards[i].title);
        if (tb.length >= 3 && (ct.indexOf(tb) >= 0 || tb.indexOf(ct) >= 0 || ct.indexOf(tb.slice(0, 4)) >= 0)) {
          cards[i].related_files.push(tp.path);
          cards[i].evidence.push(ev("file", tp.path + " (양식 파일)", fmt(tp.modified)));
          done = true;
        }
      }
      if (!done) leftover.push(tp);
    });
    if (leftover.length) cards.push({ title: "자주 쓰는 양식 파일", cycle: "비정기", status: "참고", category: "기타",
      description: "양식·템플릿 폴더에 있는 파일입니다. 각 양식을 어떤 업무에 쓰는지 적어 두면 후임자가 헤매지 않습니다.",
      related_files: leftover.map(function (f) { return f.path; }), related_people: [],
      evidence: leftover.map(function (f) { return ev("file", f.path, fmt(f.modified)); }), evidence_total: leftover.length,
      confidence: "medium", needs_reply: false, caution: "", _sort: null });

    var order = { "진행 중": 0, "정기": 1, "참고": 2, "완료": 3 };
    cards.sort(function (a, b) { return (order[a.status] - order[b.status]) || (t(b._sort) - t(a._sort)); });
    cards.forEach(function (c, i) {
      delete c._sort;
      c.id = i + 1;
      c.title = maskPii(c.title);
      c.description = maskPii(c.description);
      c.evidence = c.evidence.slice(0, 8).map(function (e) { return ev(e.kind, maskPii(e.label), e.date); });
    });
    var contacts = Array.from(people.values()).sort(function (a, b) { return b.count - a.count; });
    return { cards: cards, contacts: contacts,
      stats: { mails: mails.length, files: files.length, owner_email: owner, base_date: fmt(base), cards: cards.length, needs_reply: cards.filter(function (c) { return c.needs_reply; }).length } };
  }

  function preview(mails, files, ownerEmail) {
    var owner = detectOwner(mails, ownerEmail), od = owner ? owner.split("@").pop() : null;
    var bySender = group(mails.filter(function (m) { return m.senderEmail !== owner; }), function (m) { return m.senderEmail; });
    var senders = Array.from(bySender.entries()).map(function (e) {
      var subs = e[1].map(function (m) { return m.subject; });
      return { email: e[0], name: e[1][0].senderName, count: e[1].length, sample_subject: subs[0].slice(0, 60), suggest_exclude: looksPersonalMail(e[0], subs, od) };
    }).sort(function (a, b) { return (a.suggest_exclude === b.suggest_exclude ? 0 : a.suggest_exclude ? -1 : 1) || b.count - a.count; });
    var fc = new Map();
    files.forEach(function (f) { var k = f.path.split("/").slice(0, -1).slice(0, 3).join("/"); fc.set(k, (fc.get(k) || 0) + 1); });
    var folders = Array.from(fc.entries()).sort(function (a, b) { return a[0] < b[0] ? -1 : 1; })
      .map(function (e) { return { path: e[0], count: e[1], suggest_exclude: looksPersonalFolder(e[0]) }; });
    var dates = mails.filter(function (m) { return m.date; }).map(function (m) { return m.date.getTime(); });
    return { owner_email: owner, mail_count: mails.length, file_count: files.length, senders: senders, folders: folders,
      date_range: dates.length ? [fmt(new Date(Math.min.apply(null, dates))), fmt(new Date(Math.max.apply(null, dates)))] : null,
      undated: mails.filter(function (m) { return !m.date; }).length };
  }

  var api = { parseMailSource: parseMailSource, parseFileList: parseFileList, parseDate: parseDate, applyFilters: applyFilters,
    analyze: analyze, preview: preview, maskPii: maskPii, snippet: snippet, cleanTitle: cleanTitle, fileBase: fileBase, fmt: fmt };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.HandoverEngine = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
