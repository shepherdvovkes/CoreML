require("dotenv").config();
const axios = require("axios");
const fs = require("fs");
const path = require("path");
const { convert } = require("html-to-text");

const ZAKON_TOKEN = process.env.ZAKON_TOKEN;
if (!ZAKON_TOKEN) {
  console.error("❌ ZAKON_TOKEN не задано у .env");
  process.exit(1);
}

const CAUSE_NUMBER = "320/55287/25";
const OUTPUT_DIR = path.resolve(__dirname, "..", "resolutions_by_case", "320-55287-25");

async function searchDocumentsByCauseNum(causeNum) {
  const url = "https://court.searcher.api.zakononline.com.ua/v1/search";
  try {
    const response = await axios.get(url, {
      headers: {
        "X-App-Token": ZAKON_TOKEN,
      },
      params: {
        "where[cause_num]": causeNum,
        mode: "default",
        results: "standart",
        namespace: "sudreyestr",
        limit: 50,
      },
      timeout: 20000,
    });

    return Array.isArray(response.data) ? response.data : [];
  } catch (err) {
    console.error(
      `❌ Помилка при пошуку документів по справі ${causeNum}:`,
      err.response?.data || err.message
    );
    return [];
  }
}

async function fetchFullDocument(docId) {
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
}

(async () => {
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  console.log(`🔍 Пошук документів по справі № ${CAUSE_NUMBER}`);
  const documents = await searchDocumentsByCauseNum(CAUSE_NUMBER);

  if (documents.length === 0) {
    console.log("⚠️ Не знайдено жодного документа.");
    process.exit(1);
  }

  console.log(`📦 Знайдено ${documents.length} документів`);

  for (let i = 0; i < documents.length; i++) {
    const item = documents[i];
    const docId = item?.id || item?.doc_id;

    if (!docId) {
      console.log(`⚠️ Пропускаємо документ ${i + 1}: немає ID`);
      continue;
    }

    console.log(`\n📄 [${i + 1}/${documents.length}] "${item.title}" (ID: ${docId})`);

    // Спробуємо отримати повний текст документа
    const fullDoc = await fetchFullDocument(docId);
    
    if (!fullDoc) {
      console.log(`⚠️ Не вдалося отримати повний текст для ID ${docId}`);
      continue;
    }

    const innerData = fullDoc["0"];
    if (!innerData) {
      console.log(`⚠️ Дані документа відсутні у ключі '0' для ID ${docId}`);
      continue;
    }

    // Перевіряємо, чи це правильний документ
    if (innerData.cause_num !== CAUSE_NUMBER) {
      console.log(`⚠️ Номер справи не співпадає: ${innerData.cause_num} !== ${CAUSE_NUMBER}`);
      // Продовжуємо, можливо це правильний документ, але з іншим номером в базі
    }

    const { title, resolution, text: htmlText } = innerData;
    const plainText = convert(htmlText || "", {
      wordwrap: false,
      selectors: [{ selector: "a", format: "inline" }],
    });

    const filenameSafe = CAUSE_NUMBER.replace(/[\/\\]/g, "-");
    const JSON_FILE = path.join(OUTPUT_DIR, `full_text_${filenameSafe}_${docId}.json`);
    const TXT_FILE = path.join(OUTPUT_DIR, `full_text_${filenameSafe}_${docId}.txt`);

    // Зберігаємо JSON
    fs.writeFileSync(JSON_FILE, JSON.stringify(fullDoc, null, 2), "utf-8");
    console.log(`💾 JSON збережено у ${JSON_FILE}`);

    // Зберігаємо текст
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

    // Затримка між запитами
    await new Promise((r) => setTimeout(r, 500));
  }

  console.log(`\n✅ Готово!`);
})();

