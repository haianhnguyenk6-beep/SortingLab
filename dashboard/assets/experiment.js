"use strict";
(() => {
  const $ = selector => document.querySelector(selector);
  const names = {insertion:"Insertion",merge:"Merge",quick_last:"Quick · pivot cuối",quick_mo3:"Quick · median-of-three",heap:"Heap",timsort:"Timsort"};
  const colors = {insertion:"#d1495b",merge:"#00798c",quick_last:"#e0a100",quick_mo3:"#30638e",heap:"#794c9e",timsort:"#238543"};
  const distributions = {random:"Ngẫu nhiên",sorted:"Đã tăng dần",reversed:"Giảm dần",nearly:"Gần có thứ tự",few_unique:"Ít khóa khác nhau"};
  const numeric = value => value !== "" && value !== null && value !== undefined && Number.isFinite(Number(value));
  const fmt = (value, digits=2) => numeric(value) ? Number(value).toLocaleString("vi-VN", {minimumFractionDigits:digits,maximumFractionDigits:digits}) : "—";
  const plain = value => fmt(value,0);
  const validRows = rows => rows.filter(row => row.status === "ok" && numeric(row.median_ms) && +row.median_ms >= 0).sort((a,b) => +a.median_ms - +b.median_ms);
  let summary = [], overview = null, scale = "log";
  const numberOf = value => numeric(value) ? +value : Infinity;

  function bars(target, rows) {
    target.replaceChildren();
    const valid = validRows(rows);
    if (!valid.length) { target.textContent = "Không có phép đo hợp lệ trong cấu hình này."; return; }
    const lo = Math.min(...valid.map(row => +row.median_ms));
    const hi = Math.max(...valid.map(row => +row.median_ms));
    valid.forEach((row,index) => {
      const item = document.createElement("div");
      item.className = "rank-row";
      item.style.setProperty("--bar-color", colors[row.algorithm] || "#638b81");
      const rank = document.createElement("span"); rank.className = "rank-number"; rank.textContent = index + 1;
      const group = document.createElement("div");
      const name = document.createElement("span"); name.className = "rank-name"; name.textContent = names[row.algorithm] || row.algorithm;
      const track = document.createElement("div"); track.className = "track"; track.setAttribute("aria-hidden","true");
      const fill = document.createElement("div"); fill.className = "fill";
      // log1p supports a legitimate zero duration without NaN or an infinite bar.
      const ratio = hi === lo ? 1 : Math.log1p((+row.median_ms - lo) / Math.max(lo, 0.000001)) / Math.log1p((hi - lo) / Math.max(lo, 0.000001));
      fill.style.width = (14 + 86 * ratio) + "%";
      track.append(fill); group.append(name,track);
      const time = document.createElement("span"); time.className = "rank-time"; time.textContent = fmt(row.median_ms,3) + " ";
      const unit = document.createElement("small"); unit.textContent = "ms"; time.append(unit);
      item.append(rank,group,time); target.append(item);
    });
  }

  function cell(tr,value) { const td = document.createElement("td"); td.textContent = value; tr.append(td); return td; }
  function table(target, rows, live=false) {
    target.replaceChildren();
    const sorted = [...rows].sort((a,b) => (a.status === "ok" ? numberOf(a.median_ms) : Infinity) - (b.status === "ok" ? numberOf(b.median_ms) : Infinity));
    const winner = validRows(rows)[0];
    sorted.forEach(row => {
      const tr = document.createElement("tr");
      const name = cell(tr,"");
      const label = document.createElement("span"); label.className = "cell-algo";
      const dot = document.createElement("span"); dot.className = "dot"; dot.style.setProperty("--bar-color", colors[row.algorithm]); dot.setAttribute("aria-hidden","true");
      label.append(dot,document.createTextNode(names[row.algorithm] || row.algorithm));
      if (row === winner && !live) { const badge = document.createElement("span"); badge.className = "cell-badge"; badge.textContent = "Nhanh nhất"; label.append(badge); }
      name.append(label);
      const ok = row.status === "ok";
      cell(tr,ok ? fmt(row.median_ms,3) : "—"); cell(tr,ok ? plain(row.comparisons) : "—");
      cell(tr,ok ? plain(row.moves) : "—"); cell(tr,ok ? fmt(row.peak_kb,2) : "—");
      if (!live) {
        cell(tr,ok ? fmt(row.cv_pct,1) : "—");
        const status = cell(tr,""); const badge = document.createElement("span");
        badge.className = "badge " + (ok ? "good" : row.status === "skipped" ? "warn" : "error");
        badge.textContent = ok ? "Đã đo" : row.status === "skipped" ? "Bỏ qua" : "Lỗi";
        if (row.reason) { badge.title = row.reason; badge.tabIndex = 0; badge.setAttribute("aria-label",badge.textContent + ": " + row.reason); }
        status.append(badge);
      } else if (!ok) {
        name.append(document.createTextNode(" · " + (row.status === "skipped" ? "Bỏ qua" : "Lỗi")));
        name.title = row.reason || row.status;
      }
      target.append(tr);
    });
  }

  function refresh() {
    const distribution = $("#dist").value, n = $("#size").value;
    const image = "/figures/time_" + distribution + "_" + scale + ".svg";
    $("#chartError").hidden = true;
    $("#mainplot").src = image;
    $("#mainplot").alt = "Thời gian theo kích thước · " + distributions[distribution] + " · thang " + (scale === "log" ? "logarit" : "tuyến tính");
    $("#downloadPlot").href = image;
    $("#chartCaption").textContent = (scale === "log" ? "Hai trục logarit" : "Hai trục tuyến tính") + " · bỏ qua điểm vượt giới hạn chi phí.";
    $("#rankingMeta").textContent = distributions[distribution] + " · n = " + plain(n);
    const rows = summary.filter(row => row.distribution === distribution && String(row.n) === n);
    bars($("#bars"),rows); table($("#table"),rows);
    const valid = validRows(rows), skipped = rows.length - valid.length;
    $("#tableMeta").textContent = valid.length + "/" + rows.length + " thuật toán đã đo";
    $("#winnerName").textContent = valid.length ? names[valid[0].algorithm] || valid[0].algorithm : "Chưa có kết quả";
    $("#winnerTime").textContent = valid.length ? fmt(valid[0].median_ms,3) + " ms" : "—";
    $("#insight").textContent = "Thời gian trung vị · thang logarit. Thanh ngắn hơn là nhanh hơn." + (skipped ? " " + skipped + " thuật toán bị giới hạn chi phí." : "");
  }

  const figures = [
    ["distribution_heatmap","Ảnh hưởng của phân phối","analysis"],["small_crossover","Điểm giao ở kích thước nhỏ","analysis"],
    ["comparisons","Số phép so sánh","analysis"],["moves","Số lần ghi phần tử","analysis"],["peak_kb","Đỉnh bộ nhớ","analysis"],
    ["theory_counts","Đối chiếu công thức lý thuyết","analysis"],["cv_distribution","Độ biến thiên CV","analysis"],
    ...Object.entries(distributions).map(([key,name]) => ["sample_" + key,"Mẫu dữ liệu · " + name,"sample"]),
    ...Object.entries(distributions).flatMap(([key,name]) => [["time_"+key+"_log",name+" · Thời gian (logarit)","time"],["time_"+key+"_linear",name+" · Thời gian (tuyến tính)","time"]])
  ];
  function openFigure(src,title) {
    $("#viewTitle").textContent = title; $("#viewImg").src = src; $("#viewImg").alt = title;
    $("#viewer").showModal();
  }
  function renderGallery() {
    const category = $("#galleryCategory").value;
    const available = overview?.figures || [];
    const selected = figures.filter(([file,,group]) => (category === "all" || category === group) && available.includes(file+".svg"));
    $("#gallery").replaceChildren();
    selected.forEach(([file,title]) => {
      const button = document.createElement("button"); button.type = "button"; button.className = "thumb";
      const img = document.createElement("img"); img.src = "/figures/"+file+".svg"; img.alt = title; img.loading = "lazy";
      const label = document.createElement("span"); label.textContent = title;
      button.append(img,label); button.addEventListener("click",() => openFigure(img.src,title));
      $("#gallery").append(button);
    });
    $("#galleryCount").textContent = selected.length + " biểu đồ";
  }

  async function readJSON(url) {
    const response = await fetch(url, {cache:"no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Không đọc được dữ liệu.");
    return data;
  }
  async function load() {
    $("#retry").disabled = true; $("#kpis").setAttribute("aria-busy","true");
    try {
      const [rows,stats] = await Promise.all([readJSON("/api/summary"),readJSON("/api/overview")]);
      if (!Array.isArray(rows)) throw new Error("Kết quả thực nghiệm không hợp lệ.");
      summary = rows; overview = stats;
      $("#configCount").textContent = plain(stats.configurations);
      $("#measuredCount").textContent = plain(stats.measured);
      $("#skippedCount").textContent = plain(stats.skipped) + " cấu hình bỏ qua theo giới hạn";
      $("#observationCount").textContent = plain(stats.observations);
      $("#figureCount").textContent = plain(stats.figures.length);
      $("#seedMeta").textContent = "Seed " + stats.seed;
      $("#repeatMeta").textContent = stats.repeats + " lần lặp";
      $("#footnote").textContent = "Nguồn: bộ đo E1–E4 trong SortingLab · seed " + stats.seed + ". " + stats.high_cv + "/" + stats.measured + " cấu hình đã đo có CV trên 10%. Kết quả được đo trên một môi trường dùng chung; xem phương pháp và giới hạn trong báo cáo đi kèm.";
      $("#dataError").hidden = true;
      refresh(); renderGallery();
    } catch (error) {
      $("#dataErrorText").textContent = "Không tải được kết quả: " + error.message;
      $("#dataError").hidden = false; $("#winnerName").textContent = "Không tải được dữ liệu";
    } finally {
      $("#retry").disabled = false; $("#kpis").setAttribute("aria-busy","false");
    }
  }
  ["dist","size"].forEach(id => $("#"+id).addEventListener("change",refresh));
  document.querySelectorAll("[data-scale]").forEach(button => button.addEventListener("click",() => {
    scale = button.dataset.scale;
    document.querySelectorAll("[data-scale]").forEach(item => item.setAttribute("aria-pressed",String(item === button)));
    refresh();
  }));
  $("#mainplot").addEventListener("error",() => { $("#chartError").hidden = false; });
  $("#galleryCategory").addEventListener("change",renderGallery);
  $("#openMainplot").addEventListener("click",() => openFigure($("#mainplot").src,$("#mainplot").alt));
  $("#closeViewer").addEventListener("click",() => $("#viewer").close());
  $("#viewer").addEventListener("click",event => { if (event.target === $("#viewer")) { const r = event.target.getBoundingClientRect(); if(event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close(); } });
  $("#retry").addEventListener("click",load);
  $("#demoForm").addEventListener("submit",async event => {
    event.preventDefault();
    const controls = [...event.currentTarget.querySelectorAll("button,input,select")];
    const status = $("#demoStatus");
    const params = new URLSearchParams({n:$("#demoN").value,distribution:$("#demoDist").value,seed:$("#seed").value});
    controls.forEach(control => control.disabled = true); $("#demoForm").setAttribute("aria-busy","true");
    status.dataset.state = "loading"; status.textContent = "Đang sinh dữ liệu và đo lần lượt 6 thuật toán…";
    $("#demoResults").hidden = true; $("#demoEmpty").hidden = true;
    try {
      const data = await readJSON("/api/demo?"+params);
      table($("#demoTable"),data.rows,true); bars($("#demoBars"),data.rows);
      $("#sample").textContent = "12 phần tử đầu: " + data.first.join(", ") + "\n12 phần tử cuối: " + data.last.join(", ");
      $("#demoResults").hidden = false; status.dataset.state = "done";
      status.textContent = "Đã đo " + validRows(data.rows).length + "/6 thuật toán · " + distributions[data.distribution] + " · n = " + plain(data.n) + " · seed " + data.seed + ". Thời gian là kết quả của lần chạy này.";
    } catch (error) {
      status.dataset.state = "error"; status.textContent = "Không thể chạy: " + error.message + " Bạn có thể thử lại.";
      $("#demoEmpty").hidden = false;
    } finally {
      controls.forEach(control => control.disabled = false); $("#demoForm").removeAttribute("aria-busy");
    }
  });
  load();
})();
