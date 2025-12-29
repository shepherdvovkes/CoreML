const axios = require("axios");
const fs = require("fs");
const path = require("path");

// 📍 URL твоего сервера
const BASE_URL = "https://legal-gpt-service.onrender.com/get-legal-decisions";

// 📁 Куда сохраняем результат
const OUTPUT_DIR = path.resolve(__dirname, "..", "search_results");
const OUTPUT_FILE = path.join(OUTPUT_DIR, "result.json");

// 🔍 Тело запроса по умолчанию
const payloadTemplate = {
  query: [
    "про визнання особи такою, що втратила право користування житловим приміщенням",
    "приватизації",
    "зареєструвати місце проживання",
  ],
  paramsConfig: {
    mode: "sph04",
    target: "text",
    results: "standart",
    namespace: "sudreyestr",
    page: "1",
    limit: "10",
    // sort: "weight",
    instance: "3",
    judgement: "3",
  },
};

async function fetchAllPages() {
  const allResults = [];
  let page = 1;
  const limit = parseInt(payloadTemplate.paramsConfig.limit, 10);

  while (true) {
    const payload = {
      ...payloadTemplate,
      paramsConfig: {
        ...payloadTemplate.paramsConfig,
        page: String(page),
      },
    };

    console.log(`\n📤 Запит сторінки ${page} з параметрами:`);
    console.dir(payload, { depth: null });

    try {
      const response = await axios.post(BASE_URL, payload, {
        headers: {
          "Content-Type": "application/json",
        },
        timeout: 60000,
      });

      console.log("📤 Надсилаємо запит до API...");
      console.log("🔍 Запит:", JSON.stringify(payload, null, 2));

      const results = response.data?.results ?? [];
      console.log(`📦 Отримано ${results.length} рішень на сторінці ${page}`);

      if (results.length === 0) {
        console.log("🔚 Більше рішень немає. Завершуємо.");
        break;
      }

      results.forEach((r, i) => {
        console.log(
          `  🔹 [${i + 1}] ${r.court || "???"} — ${
            r.title?.slice(0, 60) || "Без назви"
          }...`
        );
      });

      allResults.push(...results);

      if (results.length < limit) {
        console.log("✅ Отримано менше ніж limit — це остання сторінка.");
        break;
      }

      page++;
    } catch (error) {
      console.error(`❌ Помилка на сторінці ${page}:`, error.message);
      if (error.response) {
        console.error(
          "🔻 Відповідь сервера:",
          JSON.stringify(error.response.data, null, 2)
        );
      }
      break;
    }
  }

  console.log(`\n✅ Загальна кількість рішень: ${allResults.length}`);

  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(allResults, null, 2), "utf-8");
  console.log(`💾 Усі результати збережено у: ${OUTPUT_FILE}`);
}

// ▶️ Запуск
fetchAllPages();
