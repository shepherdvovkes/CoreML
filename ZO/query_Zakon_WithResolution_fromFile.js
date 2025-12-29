require("dotenv").config();
const axios = require("axios");
const fs = require("fs");
const path = require("path");

const INPUT_FILE = path.resolve(
  __dirname,
  "..",
  "search_results",
  "result.json"
);
const OUTPUT_FILE = path.resolve(
  __dirname,
  "..",
  "search_results",
  "result_with_resolution.json"
);

const zakonToken = process.env.ZAKON_TOKEN;

async function fetchExpandedResolution(id) {
  const url = `https://court.searcher.api.zakononline.com.ua/v1/document/expanded_resolution/${id}`;
  try {
    const response = await axios.get(url, {
      headers: {
        "X-App-Token": zakonToken,
      },
      timeout: 10000,
    });
    return response.data?.expanded_resolution || null;
  } catch (err) {
    console.error(
      `❌ Ошибка получения resolution для id ${id}:`,
      err.response?.data || err.message
    );
    return null;
  }
}

(async () => {
  const data = JSON.parse(fs.readFileSync(INPUT_FILE, "utf-8"));
  const enriched = [];

  for (let i = 0; i < data.length; i++) {
    const item = data[i];
    const docId = item?.id;
    if (!docId) continue;

    console.log(
      `🔎 [${i + 1}/${data.length}] Получаем resolution для ID: ${docId}`
    );
    const expandedResolution = await fetchExpandedResolution(docId);

    enriched.push({
      ...item,
      expanded_resolution: expandedResolution,
    });

    // опционально задержка, чтобы не перегружать API
    await new Promise((r) => setTimeout(r, 300)); // 300ms
  }

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(enriched, null, 2), "utf-8");
  console.log(`✅ Готово! Файл сохранен: ${OUTPUT_FILE}`);
})();
