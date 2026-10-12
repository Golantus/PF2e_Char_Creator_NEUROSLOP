// Run against a local running application: npm install --no-save playwright; npx playwright install chromium; node tools/browser-smoke.cjs
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000},permissions:['clipboard-read','clipboard-write']});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await context.route('**/*',route=>route.request().url().startsWith('http://127.0.0.1:8765')?route.continue():route.abort());
 await page.goto('http://127.0.0.1:8765');await page.getByRole('button',{name:'Новый персонаж',exact:true}).click();await page.getByLabel('Имя персонажа').fill('Проверка браузера');
 const meta=await (await page.request.get('http://127.0.0.1:8765/api/meta')).json();
 await page.getByLabel('Класс',{exact:true}).selectOption(meta.classes.find(r=>r.name==='Друид').id);
 await page.getByLabel('Родословная',{exact:true}).selectOption(meta.ancestries.find(r=>r.name==='Человек').id);
 await page.getByLabel('Предыстория',{exact:true}).selectOption(meta.backgrounds.find(r=>r.name==='Послушник').id);
 await page.getByLabel('Уровень персонажа').selectOption('6');await page.getByRole('button',{name:'Развитие',exact:false}).click();
 const choose=async(label,values)=>{const slot=page.locator('.slot').filter({has:page.locator('.slot-header strong',{hasText:label})}).first();for(const name of values)await slot.getByRole('button',{name,exact:true}).click();};
 await choose('Повышения родословной',['Мудрость','Телосложение']);await choose('Повышения предыстории',['Интеллект','Мудрость']);await choose('Ключевая характеристика',['Мудрость']);await choose('Четыре свободных повышения',['Мудрость','Сила','Ловкость','Телосложение']);
 const order=page.locator('.slot').filter({has:page.locator('.slot-header strong',{hasText:'Орден друидов'})});await order.locator('select').selectOption({label:'Животных'});
 await choose('Навыки класса',['Медицина','Выживание','Скрытность']);
 const fifth=page.locator('.level-card').filter({has:page.getByRole('heading',{name:'5-й уровень',exact:true})});for(const name of ['Мудрость','Телосложение','Ловкость','Сила'])await fifth.locator('.slot').filter({hasText:'Повышения характеристик'}).getByRole('button',{name,exact:true}).click();
 await page.getByRole('button',{name:'Обзор',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.stat strong')?.textContent?.includes('74'));
 
 await page.getByRole('button',{name:'Способности',exact:true}).click();await page.locator('.ability-row').filter({hasText:'Зверь-компаньон'}).getByRole('button',{name:'Зверь-компаньон'}).click();
 await page.getByRole('button',{name:'Скопировать описание',exact:true}).click();await page.getByRole('button',{name:'Скопировано',exact:true}).waitFor();const clipboard=await page.evaluate(()=>navigator.clipboard.readText());const original=await(await page.request.get('http://127.0.0.1:8765/api/rule?id='+encodeURIComponent('https://pf2e-ru-translation.readthedocs.io/ru/latest/classes/druid.html#class-feat-druid-animal-companion'))).json();if(clipboard!==original.text)throw Error('Clipboard does not match full original text');
 await page.getByRole('button',{name:'Закрыть',exact:true}).click();await page.getByRole('button',{name:'Каталог',exact:true}).click();await page.getByPlaceholder('Название на русском или английском').fill('Animal Companion');await page.locator('.catalog-row').first().click();await page.locator('.catalog-detail .rule-html').waitFor();await page.getByRole('button',{name:'Закрыть',exact:true}).click();
 await page.getByRole('button',{name:'Полная сводка',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.export-text')?.value.includes('Исцеление животного'));const exported=await page.getByLabel('Текст экспорта').inputValue();if(exported.length<5000)throw Error('Export too short');
 await page.getByRole('button',{name:'Сохранить',exact:false}).first().click();await page.waitForFunction(()=>document.querySelector('.save-state')?.textContent==='Сохранено');
 await page.reload();await page.getByRole('button',{name:/Проверка браузера/}).first().click();await page.waitForFunction(()=>document.querySelector('.stat strong')?.textContent?.includes('74'));
 await page.getByRole('button',{name:'Темная тема',exact:true}).click();
 await page.setViewportSize({width:390,height:844});const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);if(overflow)throw Error('Mobile horizontal overflow');
 console.log(JSON.stringify({ok:true,errors,clipboard:clipboard.length,export:exported.length,mobileOverflow:overflow}));await browser.close();if(errors.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
