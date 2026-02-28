const messageEl = document.getElementById("message");
const postCountEl = document.getElementById("postCount");
const modelInfoEl = document.getElementById("modelInfo");
const activeKeywordsEl = document.getElementById("activeKeywords");
const summaryEl = document.getElementById("summary");
const resultTableEl = document.getElementById("resultTable");

const showMessage = (msg, isError = false) => {
  messageEl.textContent = msg;
  messageEl.style.color = isError ? "#ff9b9b" : "#d9c59f";
};

const renderKeywords = (settings) => {
  activeKeywordsEl.innerHTML = "";
  const keywords = settings.active_keywords || [];
  if (!keywords.length) {
    activeKeywordsEl.innerHTML = "<span class='label'>暂未配置关键词</span>";
    return;
  }

  keywords.forEach((keyword) => {
    const item = document.createElement("span");
    item.className = "keyword-item";
    item.textContent = keyword;
    activeKeywordsEl.appendChild(item);
  });
};

const refreshSettings = async () => {
  const res = await fetch("/api/settings");
  const data = await res.json();
  renderKeywords(data);
};

const uploadFile = async (url, file) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(url, { method: "POST", body: formData });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "请求失败");
  return data;
};

document.getElementById("uploadPostBtn").addEventListener("click", async () => {
  const file = document.getElementById("postFile").files[0];
  if (!file) return showMessage("请先选择帖子 Excel", true);

  try {
    const data = await uploadFile("/api/posts/upload", file);
    postCountEl.textContent = `已上传 ${data.post_count} 篇`;
    showMessage("帖子上传成功");
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("uploadKeywordBtn").addEventListener("click", async () => {
  const file = document.getElementById("keywordFile").files[0];
  if (!file) return showMessage("请先选择关键词 Excel", true);

  try {
    await uploadFile("/api/settings/keywords/upload", file);
    await refreshSettings();
    showMessage("关键词 Excel 导入完成");
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("addKeywordBtn").addEventListener("click", async () => {
  const input = document.getElementById("manualKeywordInput");
  const keyword = input.value.trim();
  if (!keyword) return showMessage("请输入关键词", true);

  try {
    const res = await fetch("/api/settings/keywords/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "添加失败");

    input.value = "";
    renderKeywords(data);
    showMessage("手动关键词已添加");
  } catch (error) {
    showMessage(error.message, true);
  }
});

document.getElementById("refreshSettingsBtn").addEventListener("click", refreshSettings);

document.getElementById("analyzeBtn").addEventListener("click", async () => {
  try {
    const res = await fetch("/api/analyze", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "分析失败");

    modelInfoEl.textContent = `模型：${data.model_provider} / ${data.model_name}`;
    summaryEl.textContent = `共分析 ${data.summary.post_count} 篇帖子，${data.summary.keyword_count} 个关键词，总命中 ${data.summary.total_mentions} 次。`;

    const rows = data.keywords
      .map(
        (item) =>
          `<tr><td>${item.keyword}</td><td>${item.mentions}</td><td>${item.post_hits}</td><td>${item.sample_posts
            .map((post) => post.title)
            .join(" / ")}</td></tr>`
      )
      .join("");

    resultTableEl.innerHTML = `<table><thead><tr><th>关键词</th><th>提及次数</th><th>命中帖子数</th><th>示例标题</th></tr></thead><tbody>${rows}</tbody></table>`;
    showMessage("分析完成");
  } catch (error) {
    showMessage(error.message, true);
  }
});

refreshSettings();
