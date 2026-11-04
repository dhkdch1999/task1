/* 인수인계 장부 — Word(.docx) 인수인계서 생성기
 * 외부 라이브러리 없이 OOXML 문서를 만들고 zip(무압축)으로 묶는다. 인터넷이 없어도 동작한다.
 *
 *   HandoverDocx.build(model) → Uint8Array (.docx 파일 내용)
 *   model = { title, owner, successor, baseDate, writtenDate, stats: {mails, files, excluded}, cards, contacts }
 */
(function (root) {
  "use strict";

  // ------------------------------------------------------------ zip (저장 방식, 압축 없음)
  var CRC = (function () {
    var t = new Uint32Array(256);
    for (var n = 0; n < 256; n++) { var c = n; for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
    return t;
  })();
  function crc32(b) { var c = 0xffffffff; for (var i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }
  function zip(files) {
    var enc = new TextEncoder(), parts = [], central = [], offset = 0;
    var now = new Date();
    var dosTime = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    var dosDate = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    files.forEach(function (f) {
      var name = enc.encode(f.name), data = typeof f.data === "string" ? enc.encode(f.data) : f.data, crc = crc32(data);
      var lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true);
      lh.setUint16(10, dosTime, true); lh.setUint16(12, dosDate, true); lh.setUint32(14, crc, true);
      lh.setUint32(18, data.length, true); lh.setUint32(22, data.length, true); lh.setUint16(26, name.length, true); lh.setUint16(28, 0, true);
      parts.push(new Uint8Array(lh.buffer), name, data);
      var ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true);
      ch.setUint16(12, dosTime, true); ch.setUint16(14, dosDate, true); ch.setUint32(16, crc, true);
      ch.setUint32(20, data.length, true); ch.setUint32(24, data.length, true); ch.setUint16(28, name.length, true);
      ch.setUint32(42, offset, true);
      central.push(new Uint8Array(ch.buffer), name);
      offset += 30 + name.length + data.length;
    });
    var cdSize = central.reduce(function (n, a) { return n + a.length; }, 0);
    var end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
    end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);
    var all = parts.concat(central, [new Uint8Array(end.buffer)]);
    var out = new Uint8Array(all.reduce(function (n, a) { return n + a.length; }, 0)), pos = 0;
    all.forEach(function (a) { out.set(a, pos); pos += a.length; });
    return out;
  }

  // ------------------------------------------------------------ OOXML 조각
  var C = { ink: "18222E", sub: "4C5866", mute: "7A8591", line: "C9D1DA", head: "1F4E79", headSoft: "E3ECF5", marker: "FDF4C4", alert: "B8332B",
    tab: { "진행 중": "6A46C2", "정기": "23786A", "참고": "7D8794", "완료": "8F98A3" } };
  var PAGE_W = 9638; // A4 폭 11906 - 좌우 여백 2cm(1134) × 2

  function x(s) { return String(s == null ? "" : s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function runs(segs) {
    if (typeof segs === "string") segs = [{ t: segs }];
    return segs.map(function (s) {
      var pr = (s.b ? "<w:b/>" : "") + (s.color ? '<w:color w:val="' + s.color + '"/>' : "") + (s.sz ? '<w:sz w:val="' + s.sz + '"/><w:szCs w:val="' + s.sz + '"/>' : "");
      var lines = String(s.t).split("\n");
      return lines.map(function (ln, i) {
        return "<w:r>" + (pr ? "<w:rPr>" + pr + "</w:rPr>" : "") + (i ? "<w:br/>" : "") + '<w:t xml:space="preserve">' + x(ln) + "</w:t></w:r>";
      }).join("");
    }).join("");
  }
  function p(segs, o) {
    o = o || {};
    var ppr = (o.style ? '<w:pStyle w:val="' + o.style + '"/>' : "") + (o.keepNext ? "<w:keepNext/>" : "") +
      (o.after != null || o.before != null ? '<w:spacing' + (o.before != null ? ' w:before="' + o.before + '"' : "") + (o.after != null ? ' w:after="' + o.after + '"' : "") + "/>" : "") +
      (o.align ? '<w:jc w:val="' + o.align + '"/>' : "");
    return "<w:p>" + (ppr ? "<w:pPr>" + ppr + "</w:pPr>" : "") + runs(segs) + "</w:p>";
  }
  function cell(content, o) {
    o = o || {};
    var paras = Array.isArray(content) ? content : [content];
    var tcpr = '<w:tcW w:w="' + o.w + '" w:type="dxa"/>' + (o.span ? '<w:gridSpan w:val="' + o.span + '"/>' : "") +
      (o.fill ? '<w:shd w:val="clear" w:color="auto" w:fill="' + o.fill + '"/>' : "") + '<w:vAlign w:val="' + (o.valign || "top") + '"/>';
    return "<w:tc><w:tcPr>" + tcpr + "</w:tcPr>" + (paras.length ? paras.join("") : "<w:p/>") + "</w:tc>";
  }
  function table(widths, rows, o) {
    o = o || {};
    var b = '<w:top w:val="single" w:sz="4" w:space="0" w:color="' + C.line + '"/><w:left w:val="single" w:sz="4" w:space="0" w:color="' + C.line + '"/>' +
      '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="' + C.line + '"/><w:right w:val="single" w:sz="4" w:space="0" w:color="' + C.line + '"/>' +
      '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="' + C.line + '"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="' + C.line + '"/>';
    var total = widths.reduce(function (a, c) { return a + c; }, 0);
    return '<w:tbl><w:tblPr><w:tblW w:w="' + total + '" w:type="dxa"/><w:tblBorders>' + b + '</w:tblBorders><w:tblLayout w:type="fixed"/>' +
      '<w:tblCellMar><w:top w:w="70" w:type="dxa"/><w:left w:w="110" w:type="dxa"/><w:bottom w:w="70" w:type="dxa"/><w:right w:w="110" w:type="dxa"/></w:tblCellMar>' +
      '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>' +
      "<w:tblGrid>" + widths.map(function (w) { return '<w:gridCol w:w="' + w + '"/>'; }).join("") + "</w:tblGrid>" +
      rows.map(function (r, ri) {
        var trpr = "<w:cantSplit/>" + (o.header && ri === 0 ? "<w:tblHeader/>" : "");
        var xml = r.join("");
        // keep: 마지막 행 전까지 '다음 단락과 함께'를 걸어 표 하나가 페이지 경계에서 쪼개지지 않게 한다
        if (o.keep && ri < rows.length - 1) xml = xml.replace(/<w:p><w:pPr>/g, "<w:p><w:pPr><w:keepNext/>").replace(/<w:p>(?!<w:pPr>)/g, "<w:p><w:pPr><w:keepNext/></w:pPr>");
        return "<w:tr><w:trPr>" + trpr + "</w:trPr>" + xml + "</w:tr>";
      }).join("") + "</w:tbl>";
  }
  function labelCell(text, w) { return cell(p([{ t: text, b: true, color: C.sub }], { after: 0 }), { w: w, fill: "F2F5F8" }); }
  function headCell(text, w, align) { return cell(p([{ t: text, b: true, color: "FFFFFF" }], { after: 0, align: align }), { w: w, fill: C.head, valign: "center" }); }
  function txtCell(segs, w, o) { o = o || {}; return cell(p(segs, { after: 0, align: o.align }), { w: w, fill: o.fill, span: o.span }); }

  // ------------------------------------------------------------ 문서 본문
  var ORDER = ["진행 중", "정기", "참고", "완료"];
  var CONF = { high: "근거 충분", medium: "근거 보통", low: "근거 적음 (확인 필요)", manual: "직접 추가" };

  function body(m) {
    var out = [], cards = m.cards;
    var byStatus = ORDER.map(function (s) { return { s: s, cards: cards.filter(function (c) { return c.status === s; }) }; }).filter(function (g) { return g.cards.length; });
    var no = 0, numbered = [];
    byStatus.forEach(function (g) { g.cards.forEach(function (c) { numbered.push({ n: ++no, c: c }); }); });

    // 표지 영역
    out.push(p("인수인계서", { style: "Title" }));
    out.push(p([{ t: m.title, color: C.sub, sz: 26 }], { after: 240 }));
    var W4 = [1700, 3119, 1700, 3119];
    out.push(table(W4, [
      [labelCell("인계자", W4[0]), txtCell(m.owner || "", W4[1]), labelCell("인수자", W4[2]), txtCell(m.successor || "", W4[3])],
      [labelCell("작성일", W4[0]), txtCell(m.writtenDate, W4[1]), labelCell("자료 기준일", W4[2]), txtCell(m.baseDate || "", W4[3])],
      [labelCell("분석 범위", W4[0]), txtCell("메일 " + m.stats.mails + "건, 파일 " + m.stats.files + "개" +
        (m.stats.excluded && (m.stats.excluded.mails || m.stats.excluded.files) ? " (개인 메일 " + m.stats.excluded.mails + "건, 파일 " + m.stats.excluded.files + "개 제외)" : ""), W4[1] + W4[2] + W4[3], { span: 3 })],
    ]));
    out.push(p([{ t: "이 문서는 인계자의 업무 메일과 업무 폴더 흔적을 바탕으로 자동으로 만든 초안을 인계자가 검토·수정한 것입니다. " +
      "인수자는 업무마다 확인란에 표시하고, 궁금한 점은 메모란에 적어 인계자에게 확인하세요.", color: C.mute, sz: 18 }], { before: 120, after: 240 }));

    // 업무 목록 요약
    out.push(p("1. 업무 목록", { style: "Heading1" }));
    var WS = [700, 4638, 1300, 1300, 1700];
    var rows = [[headCell("번호", WS[0], "center"), headCell("업무명", WS[1]), headCell("상태", WS[2], "center"), headCell("주기", WS[3], "center"), headCell("비고", WS[4])]];
    numbered.forEach(function (it) {
      var c = it.c;
      rows.push([txtCell(String(it.n), WS[0], { align: "center" }), txtCell([{ t: c.title, b: true }], WS[1]),
        txtCell([{ t: c.status, b: true, color: C.tab[c.status] }], WS[2], { align: "center" }), txtCell(c.cycle, WS[3], { align: "center" }),
        txtCell(c.needs_reply ? [{ t: "답장 안 한 메일 있음", b: true, color: C.alert }] : (c.caution ? "주의사항 있음" : ""), WS[4])]);
    });
    if (!numbered.length) rows.push([txtCell("등록된 업무가 없습니다.", PAGE_W, { span: 5 })]);
    out.push(table(WS, rows, { header: true }));

    // 업무별 상세
    out.push(p("2. 업무별 상세", { style: "Heading1", before: 360 }));
    var WD = [1800, 7838];
    byStatus.forEach(function (g) {
      out.push(p([{ t: g.s, color: C.tab[g.s] }, { t: "  " + g.cards.length + "건", color: C.mute }], { style: "Heading2" }));
      g.cards.forEach(function (c) {
        var n = numbered.filter(function (it) { return it.c === c; })[0].n;
        out.push(p(n + ". " + c.title, { style: "Heading3" }));
        var r = [];
        r.push([labelCell("상태 / 주기", WD[0]), txtCell([{ t: c.status, b: true, color: C.tab[c.status] }, { t: "   " + c.cycle + "   분류: " + c.category + "   " + (CONF[c.confidence] || ""), color: C.sub }], WD[1])]);
        r.push([labelCell("업무 설명", WD[0]), txtCell(c.description || "(설명을 적어 주세요)", WD[1])]);
        if (c.needs_reply) r.push([labelCell("처리 필요", WD[0]), txtCell([{ t: "상대방이 마지막으로 보낸 메일에 아직 답장하지 않았습니다. 인계 전에 처리하거나 인수자에게 넘겨 주세요.", b: true, color: C.alert }], WD[1])]);
        r.push([labelCell("주의사항", WD[0]), cell(p(c.caution ? [{ t: c.caution }] : [{ t: "(없음)", color: C.mute }], { after: 0 }), { w: WD[1], fill: c.caution ? C.marker : null })]);
        r.push([labelCell("관련 파일", WD[0]), cell(c.related_files.length ? c.related_files.map(function (f) { return p([{ t: f.split("/").pop(), b: true }, { t: "  " + f.slice(0, Math.max(0, f.lastIndexOf("/"))), color: C.mute, sz: 16 }], { after: 0 }); })
          : [p([{ t: "(없음)", color: C.mute }], { after: 0 })], { w: WD[1] })]);
        r.push([labelCell("관련 담당자", WD[0]), cell(c.related_people.length ? c.related_people.map(function (pp) { return p([{ t: pp.name, b: true }, { t: "  " + [pp.org, pp.email].filter(Boolean).join("  "), color: C.sub }], { after: 0 }); })
          : [p([{ t: "(없음)", color: C.mute }], { after: 0 })], { w: WD[1] })]);
        if (c.evidence && c.evidence.length) r.push([labelCell("판단 근거", WD[0]), cell(c.evidence.slice(0, 4).map(function (e) {
          return p([{ t: (e.kind === "mail" ? "메일  " : "파일  "), color: C.mute, sz: 16 }, { t: e.label, sz: 18 }, { t: e.date ? "  " + e.date : "", color: C.mute, sz: 16 }], { after: 0 });
        }), { w: WD[1] })]);
        r.push([labelCell("인수자 확인", WD[0]), cell([p("□ 확인함      □ 질문 있음", { after: 40 }), p([{ t: "메모:", color: C.mute }], { after: 200 })], { w: WD[1] })]);
        out.push(table(WD, r, { keep: true }));
        out.push(p("", { after: 120 }));
      });
    });
    if (!numbered.length) out.push(p([{ t: "등록된 업무가 없습니다.", color: C.mute }]));

    // 연락처
    if (m.contacts.length) {
      out.push(p("3. 업무 연락처", { style: "Heading1", before: 360 }));
      var WC = [1700, 2400, 4038, 1500];
      var cr = [[headCell("이름", WC[0]), headCell("소속", WC[1]), headCell("메일", WC[2]), headCell("주고받은 메일", WC[3], "right")]];
      m.contacts.forEach(function (pp) {
        cr.push([txtCell([{ t: pp.name, b: true }], WC[0]), txtCell(pp.org + (pp.internal ? "" : " (외부)"), WC[1]), txtCell(pp.email, WC[2]), txtCell(pp.count + "건", WC[3], { align: "right" })]);
      });
      out.push(table(WC, cr, { header: true }));
    }

    // 서명란
    out.push(p((m.contacts.length ? "4" : "3") + ". 인수인계 확인", { style: "Heading1", before: 360 }));
    out.push(p("위 업무를 인계·인수하였음을 확인합니다.", { after: 160 }));
    var WG = [1600, 2879, 2279, 2880];
    out.push(table(WG, [
      [headCell("구분", WG[0], "center"), headCell("성명", WG[1], "center"), headCell("일자", WG[2], "center"), headCell("서명", WG[3], "center")],
      [txtCell("인계자", WG[0], { align: "center" }), txtCell(m.owner || "", WG[1], { align: "center" }), txtCell("", WG[2]), cell(p("", { after: 360 }), { w: WG[3] })],
      [txtCell("인수자", WG[0], { align: "center" }), txtCell(m.successor || "", WG[1], { align: "center" }), txtCell("", WG[2]), cell(p("", { after: 360 }), { w: WG[3] })],
      [txtCell("확인자", WG[0], { align: "center" }), txtCell("", WG[1]), txtCell("", WG[2]), cell(p("", { after: 360 }), { w: WG[3] })],
    ], { header: true }));
    return out.join("");
  }

  function documentXml(m) {
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
      "<w:body>" + body(m) +
      '<w:sectPr><w:footerReference w:type="default" r:id="rId3"/><w:pgSz w:w="11906" w:h="16838"/>' +
      '<w:pgMar w:top="1418" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="567" w:gutter="0"/></w:sectPr>' +
      "</w:body></w:document>";
  }

  var FONT = '<w:rFonts w:ascii="Malgun Gothic" w:hAnsi="Malgun Gothic" w:eastAsia="맑은 고딕" w:cs="Malgun Gothic"/>';
  function stylesXml() {
    function heading(id, name, lvl, sz, color, extra) {
      return '<w:style w:type="paragraph" w:styleId="' + id + '"><w:name w:val="' + name + '"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/>' +
        '<w:pPr><w:keepNext/><w:keepLines/>' + (extra || "") + '<w:outlineLvl w:val="' + lvl + '"/></w:pPr>' +
        '<w:rPr><w:b/><w:bCs/><w:color w:val="' + color + '"/><w:sz w:val="' + sz + '"/><w:szCs w:val="' + sz + '"/></w:rPr></w:style>';
    }
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' +
      '<w:docDefaults><w:rPrDefault><w:rPr>' + FONT + '<w:color w:val="' + C.ink + '"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:lang w:val="ko-KR" w:eastAsia="ko-KR"/></w:rPr></w:rPrDefault>' +
      '<w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>' +
      '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>' +
      '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>' +
      '<w:pPr><w:spacing w:after="60"/></w:pPr><w:rPr><w:b/><w:bCs/><w:color w:val="' + C.head + '"/><w:spacing w:val="-10"/><w:sz w:val="48"/><w:szCs w:val="48"/></w:rPr></w:style>' +
      heading("Heading1", "heading 1", 0, 28, C.head, '<w:pBdr><w:bottom w:val="single" w:sz="12" w:space="4" w:color="' + C.head + '"/></w:pBdr><w:spacing w:before="240" w:after="160"/>') +
      heading("Heading2", "heading 2", 1, 24, C.ink, '<w:spacing w:before="240" w:after="120"/>') +
      heading("Heading3", "heading 3", 2, 22, C.ink, '<w:spacing w:before="160" w:after="80"/>') +
      '<w:style w:type="paragraph" w:styleId="Footer"><w:name w:val="footer"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:color w:val="' + C.mute + '"/><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr></w:style>' +
      '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:uiPriority w:val="99"/><w:semiHidden/><w:unhideWhenUsed/>' +
      '<w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>' +
      "</w:styles>";
  }
  function footerXml(m) {
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr>' +
      '<w:r><w:t xml:space="preserve">' + x(m.title) + "  ·  </w:t></w:r>" +
      '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>' +
      '<w:r><w:t xml:space="preserve"> / </w:t></w:r>' +
      '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> NUMPAGES </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>' +
      "</w:p></w:ftr>";
  }

  function build(m) {
    var created = new Date().toISOString().replace(/\.\d+Z$/, "Z");
    return zip([
      { name: "[Content_Types].xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>' +
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' +
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>' +
        '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>' +
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>' +
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>' },
      { name: "_rels/.rels", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>' +
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>' +
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>' },
      { name: "word/_rels/document.xml.rels", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' +
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>' },
      { name: "word/document.xml", data: documentXml(m) },
      { name: "word/styles.xml", data: stylesXml() },
      { name: "word/footer1.xml", data: footerXml(m) },
      { name: "docProps/core.xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">' +
        "<dc:title>" + x(m.title) + "</dc:title><dc:creator>" + x(m.owner || "인수인계 장부") + "</dc:creator>" +
        '<dcterms:created xsi:type="dcterms:W3CDTF">' + created + '</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">' + created + "</dcterms:modified></cp:coreProperties>" },
      { name: "docProps/app.xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>인수인계 장부</Application></Properties>' },
    ]);
  }

  var api = { build: build, crc32: crc32 };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.HandoverDocx = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
