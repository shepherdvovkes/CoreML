const axios = require("axios");
const fs = require("fs");
const path = require("path");
const { convert } = require("html-to-text");
require("dotenv").config();

const OUTPUT_DIR = path.resolve(
  __dirname,
  "..",
  "resolutions_by_case",
  "320-55287-25"
);
const DOC_ID = 131831617; // правильный doc_id из поиска
const FILE_NAME_BASE = "320-55287-25"; // безопасное имя для файлов

const JSON_FILE = path.join(OUTPUT_DIR, `full_text_${FILE_NAME_BASE}.json`);
const TXT_FILE = path.join(OUTPUT_DIR, `full_text_${FILE_NAME_BASE}.txt`);

const ZAKON_TOKEN = process.env.ZAKON_TOKEN;
if (!ZAKON_TOKEN) {
  console.error("❌ ZAKON_TOKEN не задано у .env");
  process.exit(1);
}

const fetchFullDocument = async (docId) => {
  const url = `https://court.searcher.api.zakononline.com.ua/v1/document/by/number/${docId}`;
  try {
    const response = await axios.get(url, {
      headers: {
        "X-App-Token": ZAKON_TOKEN,
        Accept: "application/json",
      },
      timeout: 30000,
    });

    if (response.data && typeof response.data === "object") {
      return { docId, ...response.data };
    } else {
      console.warn(`⚠️ Порожня відповідь для docId ${docId}`);
      return null;
    }
  } catch (error) {
    console.error(`❌ Помилка для docId ${docId}: ${error.message}`);
    return null;
  }
};

(async () => {
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const fullDoc = await fetchFullDocument(DOC_ID);
  if (!fullDoc) {
    console.error("❌ Документ не завантажено.");
    process.exit(1);
  }

  // Сохраняем как JSON
  fs.writeFileSync(JSON_FILE, JSON.stringify(fullDoc, null, 2), "utf-8");
  console.log(`💾 JSON збережено у ${JSON_FILE}`);

  const innerData = fullDoc["0"];
  if (!innerData) {
    console.error("❌ Дані документа відсутні у ключі '0'");
    process.exit(1);
  }

  const { title, resolution, text: htmlText } = innerData;
  const plainText = convert(htmlText || "", {
    wordwrap: false,
    selectors: [{ selector: "a", format: "inline" }],
  });

  const composed = [
    `📄 ${title || "[без назви]"}`,
    resolution ? `🧾 ${resolution}` : "",
    "\n📚 Повний текст:",
    plainText.trim() || "[текст відсутній]",
  ]
    .join("\n\n")
    .trim();

  fs.writeFileSync(TXT_FILE, composed, "utf-8");
  console.log(`📝 Текст збережено у ${TXT_FILE}`);
})();
