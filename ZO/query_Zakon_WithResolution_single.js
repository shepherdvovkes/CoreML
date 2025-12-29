require("dotenv").config();
const axios = require("axios");
const fs = require("fs");
const path = require("path");

const zakonToken = process.env.ZAKON_TOKEN;
const docId = 113041637;

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
  console.log(`🔍 Получаем resolution для doc_id: ${docId}`);
  const resolution = await fetchExpandedResolution(docId);

  if (resolution) {
    console.log(`✅ Expanded resolution:\n\n${resolution}`);

    const outputDir = path.resolve(__dirname, "..", "resolutions");
    const outputFile = path.join(outputDir, `${docId}.json`);

    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    const outputData = {
      doc_id: docId,
      expanded_resolution: resolution,
      fetched_at: new Date().toISOString(),
    };

    fs.writeFileSync(outputFile, JSON.stringify(outputData, null, 2), "utf-8");
    console.log(`💾 JSON сохранён в файл: ${outputFile}`);
  } else {
    console.log("⚠️ Resolution не найден.");
  }
})();
