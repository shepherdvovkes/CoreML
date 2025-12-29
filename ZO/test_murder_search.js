require("dotenv").config();
const axios = require("axios");

const ZAKON_TOKEN = process.env.ZAKON_TOKEN || process.env.ZAKONONLINE_TOKEN;
const ZAKON_API_URL = "https://court.searcher.api.zakononline.com.ua/v1/search";

async function testSearch(query, year) {
  const dateFrom = `${year}-01-01`;
  const dateTo = `${year}-12-31`;

  console.log(`\n🔍 Тест пошуку: "${query}" за ${year} рік`);
  console.log("Параметри:");
  console.log("  - Без обмеження за інстанцією");
  console.log("  - Без обмеження за типом рішення");
  console.log("  - Діапазон дат:", dateFrom, "-", dateTo);

  const params = {
    mode: "default",
    results: "standart",
    namespace: "sudreyestr",
    limit: 50,
    page: "1",
    "where[adjudication_date_from]": dateFrom,
    "where[adjudication_date_to]": dateTo,
    q: query,
  };

  try {
    const response = await axios.get(ZAKON_API_URL, {
      headers: {
        "X-App-Token": ZAKON_TOKEN,
      },
      params,
      timeout: 30000,
    });

    const results = Array.isArray(response.data) ? response.data : [];
    
    // Фільтрація за роком
    const filteredResults = results.filter((item) => {
      if (!item.adjudication_date) return false;
      const date = new Date(item.adjudication_date);
      return date.getFullYear() === year;
    });

    console.log(`\n📊 Результати:`);
    console.log(`  - Всього знайдено: ${results.length}`);
    console.log(`  - Відфільтровано за роком: ${filteredResults.length}`);
    
    if (filteredResults.length > 0) {
      console.log(`\n  Перші 3 справи:`);
      filteredResults.slice(0, 3).forEach((item, i) => {
        console.log(`    [${i+1}] ${item.title?.substring(0, 70)}...`);
      });
    }

    return filteredResults.length;
  } catch (error) {
    console.error(`❌ Помилка:`, error.message);
    if (error.response) {
      console.error("🔻 Відповідь сервера:", JSON.stringify(error.response.data, null, 2));
    }
    return 0;
  }
}

(async () => {
  console.log("🧪 ТЕСТОВИЙ ПОШУК ВБИВСТВ");
  console.log("=".repeat(60));
  
  const year = 2024;
  const queries = ["вбивство", "убивство", "вбивство стаття 115"];
  
  let total = 0;
  for (const query of queries) {
    const count = await testSearch(query, year);
    total += count;
    await new Promise((r) => setTimeout(r, 1000));
  }
  
  console.log("\n" + "=".repeat(60));
  console.log(`📈 Всього знайдено унікальних справ: ${total}`);
  console.log("=".repeat(60));
})();

