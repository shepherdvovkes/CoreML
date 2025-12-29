require("dotenv").config();
const axios = require("axios");
const fs = require("fs");
const path = require("path");

// 🔑 Токен API (підтримка обох варіантів назви)
const ZAKON_TOKEN = process.env.ZAKON_TOKEN || process.env.ZAKONONLINE_TOKEN;
if (!ZAKON_TOKEN) {
  console.error("❌ ZAKON_TOKEN або ZAKONONLINE_TOKEN не задано у .env");
  console.error("💡 Додайте один з цих токенів до .env файлу:");
  console.error("   ZAKON_TOKEN=your_token_here");
  console.error("   або");
  console.error("   ZAKONONLINE_TOKEN=your_token_here");
  process.exit(1);
}

// 📁 Папка для результатів
const OUTPUT_DIR = path.resolve(__dirname, "..", "murder_cases_statistics");
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// 📝 Лог-файл для виводу
const LOG_FILE = path.join(OUTPUT_DIR, `run_${new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)}.log`);
let logStream = null;

// Функція для одночасного виводу у консоль і файл
function log(message) {
  const timestamp = new Date().toLocaleTimeString('uk-UA');
  const logMessage = `[${timestamp}] ${message}`;
  
  // Вивід у консоль
  console.log(message);
  
  // Запис у файл
  if (!logStream) {
    logStream = fs.createWriteStream(LOG_FILE, { flags: 'a' });
  }
  logStream.write(logMessage + '\n');
}

// Перехоплення console.log для логування
const originalConsoleLog = console.log;
console.log = function(...args) {
  originalConsoleLog.apply(console, args);
  if (logStream) {
    const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
    logStream.write(`[${new Date().toLocaleTimeString('uk-UA')}] ${message}\n`);
  }
};

// 📊 Роки для аналізу
const YEARS = [2022, 2023, 2024];

// 🔍 Запити для пошуку вбивств (всі типи)
const MURDER_QUERIES = [
  "вбивство",
  "убивство",
  "вбивство з особливою жорстокістю",
  "вбивство за попередньою змовою",
  "вбивство двох або більше осіб",
  "вбивство в стані афекту",
  "вбивство матір'ю новонародженої дитини",
  "вбивство при перевищенні меж необхідної оборони",
  "вбивство при перевищенні заходів, необхідних для затримання",
  "вбивство з необережності",
  "вбивство стаття 115",
  "вбивство стаття 116",
  "вбивство стаття 117",
  "вбивство стаття 118",
  "вбивство стаття 119",
  "вбивство стаття 121",
];

// 🌐 Базовий URL для семантичного пошуку
const SEMANTIC_SEARCH_URL = "https://legal-gpt-service.onrender.com/get-legal-decisions";

// 🌐 Базовий URL для прямого API ZakonOnline
const ZAKON_API_URL = "https://court.searcher.api.zakononline.com.ua/v1/search";

// ⚙️ Налаштування retry для обробки rate limiting
const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 2000; // 2 секунди

/**
 * Семантичний пошук через власний API сервіс з retry логікою
 */
async function semanticSearch(query, year, page = 1, retryCount = 0) {
  const MAX_RETRIES = 3;
  const payload = {
    query: [query],
    paramsConfig: {
      mode: "sph04",
      target: "text",
      results: "standart",
      namespace: "sudreyestr",
      page: String(page),
      limit: "50",
      // Прибрано обмеження за інстанцією - шукаємо в усіх
      // Прибрано обмеження за типом рішення - шукаємо всі типи
    },
  };

  try {
    const response = await axios.post(SEMANTIC_SEARCH_URL, payload, {
      headers: {
        "Content-Type": "application/json",
      },
      timeout: 60000,
    });

    const results = response.data?.results ?? [];
    
    // Фільтруємо за роком
    const filteredResults = results.filter((item) => {
      if (!item.adjudication_date) return false;
      const date = new Date(item.adjudication_date);
      return date.getFullYear() === year;
    });

    return {
      results: filteredResults,
      total: response.data?.total ?? 0,
      hasMore: filteredResults.length === parseInt(payload.paramsConfig.limit, 10),
    };
  } catch (error) {
    // Обробка помилки 429 (Too Many Requests) з retry
    if (error.response?.status === 429 && retryCount < MAX_RETRIES) {
      const waitTime = Math.pow(2, retryCount) * BASE_RETRY_DELAY; // Експоненційна затримка: 2s, 4s, 8s
      console.log(`  ⏳ Rate limit досягнуто (429). Очікування ${waitTime/1000} сек перед повторною спробою ${retryCount + 1}/${MAX_RETRIES}...`);
      await new Promise((r) => setTimeout(r, waitTime));
      return semanticSearch(query, year, page, retryCount + 1);
    }
    
    console.error(`❌ Помилка семантичного пошуку для "${query}" (${year}):`, error.message);
    if (error.response?.status === 429) {
      console.error(`  ⚠️ Rate limit досягнуто після ${retryCount} спроб. Пропускаємо цей запит.`);
    }
    return { results: [], total: 0, hasMore: false };
  }
}

/**
 * Прямий пошук через API ZakonOnline з retry логікою
 */
async function directSearch(query, year, page = 1, retryCount = 0) {
  // Прямий API не підтримує adjudication_date_from, тому використовуємо тільки текстовий пошук
  // Фільтрацію за роком робимо вручну після отримання результатів
  const params = {
    mode: "default",
    results: "standart",
    namespace: "sudreyestr",
    limit: 50,
    page: String(page),
    // Не використовуємо where[adjudication_date_from] - API не підтримує
    q: query, // Текстовий пошук
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
    
    // Додаткова фільтрація за роком (на випадок, якщо API не відфільтрував)
    const filteredResults = results.filter((item) => {
      if (!item.adjudication_date) return false;
      const date = new Date(item.adjudication_date);
      return date.getFullYear() === year;
    });
    
    return {
      results: filteredResults,
      total: filteredResults.length,
      hasMore: results.length === 50, // Перевіряємо оригінальну кількість
    };
  } catch (error) {
    // Обробка помилки 429 (Too Many Requests) з retry
    if (error.response?.status === 429 && retryCount < MAX_RETRIES) {
      const waitTime = Math.pow(2, retryCount) * BASE_RETRY_DELAY; // Експоненційна затримка: 2s, 4s, 8s
      console.log(`  ⏳ Rate limit досягнуто (429). Очікування ${waitTime/1000} сек перед повторною спробою ${retryCount + 1}/${MAX_RETRIES}...`);
      await new Promise((r) => setTimeout(r, waitTime));
      return directSearch(query, year, page, retryCount + 1);
    }
    
    console.error(`❌ Помилка прямого пошуку для "${query}" (${year}):`, error.message);
    if (error.response?.status === 429) {
      console.error(`  ⚠️ Rate limit досягнуто після ${retryCount} спроб. Пропускаємо цей запит.`);
    } else if (error.response) {
      console.error("🔻 Відповідь сервера:", JSON.stringify(error.response.data, null, 2));
    }
    return { results: [], total: 0, hasMore: false };
  }
}

/**
 * Отримати всі сторінки результатів
 */
async function fetchAllPages(searchFunction, query, year, statsCallback) {
  const allResults = [];
  const seenIds = new Set(); // Для уникнення дублікатів
  let page = 1;
  let hasMore = true;
  let totalFound = 0;
  let newOnThisPage = 0;

  while (hasMore) {
    const beforeCount = allResults.length;
    console.log(`  📄 Сторінка ${page}...`);
    
    const response = await searchFunction(query, year, page);
    const results = response.results || [];

    // Додаємо тільки унікальні результати
    for (const item of results) {
      const id = item.id || item.doc_id;
      if (id && !seenIds.has(id)) {
        seenIds.add(id);
        allResults.push(item);
        newOnThisPage++;
      }
    }

    totalFound += results.length;
    const duplicates = results.length - newOnThisPage;
    
    if (results.length > 0) {
      console.log(`     ✓ Отримано: ${results.length} справ (нових: ${newOnThisPage}, дублікатів: ${duplicates})`);
      console.log(`     📊 Всього унікальних: ${allResults.length}`);
    }

    hasMore = response.hasMore && results.length > 0;
    page++;
    newOnThisPage = 0;

    // Затримка між запитами (збільшена для уникнення rate limiting)
    if (hasMore) {
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  if (statsCallback) {
    statsCallback(allResults);
  }

  return allResults;
}

/**
 * Аналіз статистики справ
 */
function analyzeCases(cases) {
  const stats = {
    total: cases.length,
    byType: {},
    byInstance: {},
    byMonth: {},
  };

  cases.forEach((item) => {
    // Тип рішення
    const title = item.title || '';
    const typeMatch = title.match(/^(Вирок|Постанова|Ухвала|Рішення|Окрема думка)/);
    const type = typeMatch ? typeMatch[1] : 'Інше';
    stats.byType[type] = (stats.byType[type] || 0) + 1;

    // Інстанція
    const instanceMatch = title.match(/(перша|апеляційн|касаційн|Верховний|Велика Палата)/i);
    const instance = instanceMatch ? instanceMatch[1] : 'невідомо';
    stats.byInstance[instance] = (stats.byInstance[instance] || 0) + 1;

    // Місяць
    if (item.date) {
      const date = new Date(item.date);
      const month = date.toLocaleString('uk-UA', { month: 'long' });
      stats.byMonth[month] = (stats.byMonth[month] || 0) + 1;
    }
  });

  return stats;
}

/**
 * Вивести статистику
 */
function printStats(stats, label = '') {
  console.log(`\n  📊 Статистика ${label}:`);
  console.log(`     Всього справ: ${stats.total}`);
  
  if (Object.keys(stats.byType).length > 0) {
    console.log(`     За типами рішень:`);
    Object.entries(stats.byType)
      .sort((a, b) => b[1] - a[1])
      .forEach(([type, count]) => {
        console.log(`       • ${type}: ${count}`);
      });
  }
  
  if (Object.keys(stats.byInstance).length > 0) {
    console.log(`     За інстанціями:`);
    Object.entries(stats.byInstance)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .forEach(([inst, count]) => {
        console.log(`       • ${inst}: ${count}`);
      });
  }
}

/**
 * Пошук вбивств за рік
 */
async function searchMurdersForYear(year, useSemantic = true) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`🔍 Пошук вбивств за ${year} рік (${useSemantic ? 'семантичний' : 'прямий API'})...`);
  console.log('='.repeat(60));

  const allResults = [];
  const searchFunction = useSemantic ? semanticSearch : directSearch;
  const startTime = Date.now();

  // Шукаємо за кожним запитом
  // Використовуємо всі запити для максимального покриття
  // Але спочатку пробуємо найзагальніші терміни
  const searchQueries = MURDER_QUERIES; // Використовуємо всі запити
  
  for (let i = 0; i < searchQueries.length; i++) {
    const query = searchQueries[i];
    const progress = ((i + 1) / searchQueries.length * 100).toFixed(1);
    console.log(`\n  🔎 [${i + 1}/${searchQueries.length}] (${progress}%) Запит: "${query}"`);
    console.log(`     Загальна кількість знайдених справ: ${allResults.length}`);

    const beforeCount = allResults.length;
    const results = await fetchAllPages(searchFunction, query, year, (cases) => {
      // Статистика по поточному запиту
      if (cases.length > 0) {
        const queryStats = analyzeCases(cases);
        printStats(queryStats, `по запиту "${query}"`);
      }
    });
    
    const newCases = results.length;
    const addedToTotal = results.filter(r => {
      const id = r.id || r.doc_id;
      return !allResults.some(existing => (existing.id || existing.doc_id) === id);
    }).length;

    console.log(`  ✅ Запит завершено: знайдено ${newCases} справ, додано ${addedToTotal} нових`);
    allResults.push(...results);

    // Загальна статистика після кожного запиту
    const uniqueResults = [];
    const seenIds = new Set();
    for (const item of allResults) {
      const id = item.id || item.doc_id;
      if (id && !seenIds.has(id)) {
        seenIds.add(id);
        uniqueResults.push(item);
      }
    }
    
    const currentStats = analyzeCases(uniqueResults);
    console.log(`\n  📈 Загальна статистика після ${i + 1} запитів:`);
    console.log(`     Унікальних справ: ${uniqueResults.length}`);
    console.log(`     За типами: ${Object.entries(currentStats.byType).map(([k,v]) => `${k}(${v})`).join(', ')}`);

    // Затримка між різними запитами (збільшена для уникнення rate limiting)
    const delay = useSemantic ? 3000 : 2000; // Збільшено з 1500 до 3000 для семантичного пошуку
    if (i < searchQueries.length - 1) {
      console.log(`  ⏸️  Пауза ${delay/1000} сек перед наступним запитом...`);
      await new Promise((r) => setTimeout(r, delay));
    }
  }

  // Видаляємо дублікати за ID
  const uniqueResults = [];
  const seenIds = new Set();

  for (const item of allResults) {
    const id = item.id || item.doc_id;
    if (id && !seenIds.has(id)) {
      seenIds.add(id);
      uniqueResults.push(item);
    }
  }

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const finalStats = analyzeCases(uniqueResults);

  console.log(`\n${'='.repeat(60)}`);
  console.log(`📊 ПІДСУМОК ЗА ${year} РІК`);
  console.log('='.repeat(60));
  console.log(`  ⏱️  Час виконання: ${elapsed} сек`);
  console.log(`  📦 Всього знайдено: ${allResults.length} справ`);
  console.log(`  ✅ Унікальних справ: ${uniqueResults.length}`);
  console.log(`  🔄 Дублікатів видалено: ${allResults.length - uniqueResults.length}`);
  
  printStats(finalStats, `за ${year} рік`);
  console.log('='.repeat(60));

  return uniqueResults;
}

/**
 * Головна функція
 */
async function main() {
  console.log("🚀 Запуск статистики вбивств за 2022-2024 роки\n");
  console.log("=" .repeat(60));

  const statistics = {
    years: {},
    total: 0,
    method: "semantic", // або "direct"
  };

  // Використовуємо семантичний пошук (прямий API має проблеми з фільтрацією за датою)
  let useSemantic = true;

  for (const year of YEARS) {
    try {
      const results = await searchMurdersForYear(year, useSemantic);
      
      statistics.years[year] = {
        count: results.length,
        cases: results.map((item) => ({
          id: item.id || item.doc_id,
          title: item.title,
          date: item.adjudication_date,
          court: item.court,
          url: item.url,
        })),
      };

      statistics.total += results.length;

      // Зберігаємо проміжні результати
      const yearFile = path.join(OUTPUT_DIR, `murders_${year}.json`);
      fs.writeFileSync(
        yearFile,
        JSON.stringify(statistics.years[year], null, 2),
        "utf-8"
      );
      console.log(`💾 Результати збережено: ${yearFile}`);

      // Затримка між роками
      await new Promise((r) => setTimeout(r, 2000));
    } catch (error) {
      console.error(`❌ Помилка обробки ${year} року:`, error.message);
      
      // Якщо семантичний пошук не працює, пробуємо прямий API
      if (useSemantic && error.message.includes("timeout")) {
        console.log("\n⚠️ Семантичний пошук не працює, переходимо на прямий API...");
        useSemantic = false;
        statistics.method = "direct";
        
        // Повторюємо для цього року з прямим API
        const results = await searchMurdersForYear(year, false);
        statistics.years[year] = {
          count: results.length,
          cases: results.map((item) => ({
            id: item.id || item.doc_id,
            title: item.title,
            date: item.adjudication_date,
            court: item.court,
            url: item.url,
          })),
        };
        statistics.total += results.length;
      }
    }
  }

  // Зберігаємо загальну статистику
  const summaryFile = path.join(OUTPUT_DIR, "summary.json");
  fs.writeFileSync(summaryFile, JSON.stringify(statistics, null, 2), "utf-8");

  // Виводимо підсумок
  console.log("\n" + "=".repeat(60));
  console.log("📊 ЗАГАЛЬНИЙ ПІДСУМОК СТАТИСТИКИ ВБИВСТВ");
  console.log("=".repeat(60));
  console.log(`\nМетод пошуку: ${statistics.method === "semantic" ? "Семантичний" : "Прямий API"}`);
  console.log("\nКількість справ по роках:");
  
  const yearStats = [];
  for (const year of YEARS) {
    const yearData = statistics.years[year];
    const count = yearData?.count || 0;
    const cases = yearData?.cases || [];
    
    // Аналіз по роках
    const stats = analyzeCases(cases);
    yearStats.push({ year, count, stats });
    
    console.log(`\n  ${year}: ${count} справ`);
    if (count > 0) {
      console.log(`     Типи: ${Object.entries(stats.byType).map(([k,v]) => `${k}(${v})`).join(', ')}`);
    }
  }
  
  console.log(`\n📈 Всього унікальних справ: ${statistics.total}`);
  
  // Динаміка
  if (yearStats.length >= 2) {
    console.log(`\n📉 Динаміка змін:`);
    for (let i = 1; i < yearStats.length; i++) {
      const prev = yearStats[i-1].count;
      const curr = yearStats[i].count;
      const change = curr - prev;
      const percent = prev > 0 ? ((change / prev) * 100).toFixed(1) : 0;
      const arrow = change > 0 ? '📈' : change < 0 ? '📉' : '➡️';
      console.log(`     ${yearStats[i-1].year} → ${yearStats[i].year}: ${arrow} ${change > 0 ? '+' : ''}${change} справ (${percent > 0 ? '+' : ''}${percent}%)`);
    }
  }
  
  console.log(`\n💾 Повна статистика збережена: ${summaryFile}`);
  console.log("=".repeat(60));
}

// Запуск
main().catch((error) => {
  console.error("❌ Критична помилка:", error);
  process.exit(1);
});

