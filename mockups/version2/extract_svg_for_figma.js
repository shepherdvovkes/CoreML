const fs = require('fs');
const path = require('path');

// Читаем HTML файл
const htmlPath = path.join(__dirname, 'mockups-for-figma.html');
const htmlContent = fs.readFileSync(htmlPath, 'utf-8');

// Регулярное выражение для поиска SVG элементов
const svgRegex = /<svg[^>]*>[\s\S]*?<\/svg>/gi;
const svgMatches = htmlContent.match(svgRegex);

if (!svgMatches) {
  console.log('SVG элементы не найдены');
  process.exit(1);
}

// Создаем директорию для SVG файлов
const svgDir = path.join(__dirname, 'svg_for_figma');
if (!fs.existsSync(svgDir)) {
  fs.mkdirSync(svgDir, { recursive: true });
}

// Извлекаем информацию о каждом экране и сохраняем SVG
let screenIndex = 0;
const screenRegex = /<div class="screen[^"]*">[\s\S]*?<strong>([^<]+)<\/strong>[\s\S]*?<code>([^<]+)<\/code>/gi;
let screenMatch;
const screens = [];

while ((screenMatch = screenRegex.exec(htmlContent)) !== null) {
  screens.push({
    title: screenMatch[1].trim(),
    route: screenMatch[2].trim(),
  });
}

console.log(`Найдено ${svgMatches.length} SVG элементов и ${screens.length} экранов`);

// Сохраняем каждый SVG
svgMatches.forEach((svg, index) => {
  const screenInfo = screens[index] || { title: `Screen ${index + 1}`, route: '' };
  const fileName = `screen_${String(index + 1).padStart(2, '0')}_${screenInfo.route.replace(/\//g, '_').replace(/#/g, '_') || `screen${index + 1}`}.svg`;
  const filePath = path.join(svgDir, fileName);
  
  // Добавляем XML декларацию и оборачиваем в правильный SVG
  const svgWithHeader = `<?xml version="1.0" encoding="UTF-8"?>
<!-- ${screenInfo.title} - ${screenInfo.route} -->
${svg}
`;
  
  fs.writeFileSync(filePath, svgWithHeader, 'utf-8');
  console.log(`✓ Сохранен: ${fileName}`);
});

// Создаем README с инструкциями
const readme = `# SVG файлы для импорта в Figma

## Инструкция по импорту:

1. **Через Drag & Drop:**
   - Откройте Figma Desktop приложение
   - Перетащите SVG файлы из этой папки прямо в Figma
   - Figma автоматически создаст фреймы для каждого SVG

2. **Через меню:**
   - File → Import → выберите SVG файлы
   - Или используйте плагин "SVG Import"

3. **Через плагин:**
   - Установите плагин "SVG Import" или "HTML to Design"
   - Используйте плагин для массового импорта

## Структура файлов:
${svgMatches.map((svg, index) => {
  const screen = screens[index] || { title: `Screen ${index + 1}`, route: '' };
  return `- \`screen_${String(index + 1).padStart(2, '0')}_${screen.route.replace(/\//g, '_').replace(/#/g, '_') || `screen${index + 1}`}.svg\` - ${screen.title}`;
}).join('\n')}

## Примечания:
- Все SVG имеют размер 390x844 (стандартный размер мобильного экрана)
- ViewBox установлен на "0 0 390 844"
- После импорта вы можете масштабировать и организовывать фреймы по своему усмотрению
`;

fs.writeFileSync(path.join(svgDir, 'README.md'), readme, 'utf-8');
console.log(`\n✓ Создан README.md с инструкциями`);
console.log(`\nВсего сохранено: ${svgMatches.length} SVG файлов в папку: ${svgDir}`);

