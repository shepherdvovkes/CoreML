require("dotenv").config();
const axios = require("axios");
const fs = require("fs");
const path = require("path");

const zakonToken = process.env.ZAKON_TOKEN;
const causeNumbers = ["320/55287/25"];

const outputDir = path.resolve(
  __dirname,
  "..",
  "resolutions_by_case/320-55287-25"
);

if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

async function searchDocumentsByCauseNum(causeNum) {
  const url = "https://court.searcher.api.zakononline.com.ua/v1/search";
  try {
    const response = await axios.get(url, {
      headers: {
        "X-App-Token": zakonToken,
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

async function fetchExpandedResolution(docId) {
  const url = `https://court.searcher.api.zakononline.com.ua/v1/document/expanded_resolution/${docId}`;
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
      `⚠️ Помилка отримання resolution для doc_id ${docId}:`,
      err.response?.data || err.message
    );
    return null;
  }
}

async function processCauseNumber(causeNumber) {
  console.log(`\n🔍 Обробка справи № ${causeNumber}`);
  const documents = await searchDocumentsByCauseNum(causeNumber);

  if (documents.length === 0) {
    console.log("⚠️ Не знайдено жодного документа.");
    return;
  }

  const enriched = [];

  for (let i = 0; i < documents.length; i++) {
    const item = documents[i];
    const docId = item?.id;

    console.log(
      `📄 [${i + 1}/${documents.length}] "${item.title}" (ID: ${docId})`
    );

    const resolution = await fetchExpandedResolution(docId);

    enriched.push({
      doc_id: docId,
      title: item.title,
      date: item.adjudication_date,
      url: item.url,
      expanded_resolution: resolution,
    });

    await new Promise((r) => setTimeout(r, 300));
  }

  enriched.sort((a, b) => new Date(b.date) - new Date(a.date));

  const filenameSafe = causeNumber.replace(/[\/\\]/g, "-");
  const outputFile = path.join(outputDir, `${filenameSafe}.json`);
  fs.writeFileSync(outputFile, JSON.stringify(enriched, null, 2), "utf-8");

  console.log(
    `✅ Збережено ${enriched.length} резолюцій у файл: ${outputFile}`
  );
}

(async () => {
  for (const causeNumber of causeNumbers) {
    await processCauseNumber(causeNumber);
  }
})();
