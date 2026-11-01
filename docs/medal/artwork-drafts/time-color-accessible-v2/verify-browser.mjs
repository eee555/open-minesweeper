/** Prepare a local browser check or collect its --dump-dom results. */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
if (process.argv[2] === 'collect') {
    const text = readFileSync(join(root, '.browser-check-dom.html'), 'utf8');
    const match = /<pre id="browser-verification">([\s\S]*?)<\/pre>/.exec(text);
    if (!match) throw new Error('Browser did not produce a verification result.');
    const result = JSON.parse(match[1].replaceAll('&quot;', '"').replaceAll('&gt;', '>').replaceAll('&lt;', '<').replaceAll('&amp;', '&'));
    writeFileSync(join(root, 'exports/browser-verification.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result));
    if (!result.passed) process.exitCode = 1;
} else {
    const app = readFileSync(join(root, 'index.html'), 'utf8');
    const check = String.raw`<script>
(async () => {
 const key='medal-palette-review-reload-check', $=id=>document.getElementById(id), checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label)};
 const change=(el,value)=>{el.value=value;el.dispatchEvent(new Event('change',{bubbles:true}))};
 const hex=key=>document.querySelector('input[data-hex][data-key="'+key+'"]');
 const finish=result=>{document.querySelectorAll('script').forEach(s=>s.remove());const pre=document.createElement('pre');pre.id='browser-verification';pre.hidden=true;pre.textContent=JSON.stringify(result);document.body.append(pre)};
 try {
  const resumed=sessionStorage.getItem(key);
  if(resumed){
   checks.push(...JSON.parse(resumed));sessionStorage.removeItem(key);
   assert(hex('tier-1').value==='#456789','preferences restored after a real reload');
   assert($('storage-status').textContent.includes('恢复'),'restored status is truthful');
   $('reset').click();$('theme').click();change($('vision'),'deuteranopia');
   assert(document.documentElement.scrollWidth<=window.innerWidth,'no horizontal page overflow');
   finish({passed:true,method:'Chrome headless, actual DOM and SVG filters',checks});return;
  }
  $('reset').click();
  assert(document.querySelectorAll('.tier-card').length===5,'five tier previews');
  assert(document.querySelectorAll('#stages .stage').length===11,'all eleven beginner thresholds');
  change(hex('tier-1'),'#3466AA');
  assert(document.querySelector('[data-color-label="1"]').textContent==='#3466AA','tier color updates its label');
  assert(document.querySelector('#tier-1 feFuncB').getAttribute('tableValues').includes('0.666667'),'tier filter updates its actual channel values');
  assert(hex('stage-20000').value==='#3466AA'&&hex('stage-15000').value==='#3466AA','unmodified thresholds follow their tier');
  change(hex('stage-20000'),'#F0B22D');
  assert(document.querySelector('[data-override-tag="20000"]').textContent==='单独设色','exact threshold override is explicit');
  assert(hex('stage-15000').value==='#3466AA','threshold override does not recolor its neighbor');
  document.querySelector('[data-clear-stage="20000"]').click();
  assert(hex('stage-20000').value==='#3466AA','follow-tier clears the exact override');
  change(hex('tier-1'),'#oops');
  assert($('error').textContent.length>0&&document.querySelector('[data-color-label="1"]').textContent==='#3466AA','invalid HEX does not change the active palette');
  change(hex('tier-1'),'#345678');
  assert(!$('error').textContent,'valid input clears its error');
  const tierStar=document.querySelector('[data-shape-star]'),beginnerStar=document.querySelector('#stages .star').src;
  const old=tierStar.src;change($('difficulty'),'3');
  assert(tierStar.src!==old&&document.querySelector('#stages .star').src===beginnerStar,'expert shape preview leaves beginner threshold stars unchanged');
  assert(document.querySelector('[data-shape-label]').getAttribute('aria-label').includes('3 星'),'shape preview accessible name includes difficulty');
  for(const mode of ['normal','protanopia','deuteranopia','tritanopia','gray']){
   change($('vision'),mode);
   assert(document.body.style.getPropertyValue('--vision-filter')===(mode==='normal'?'none':mode==='gray'?'grayscale(1)':'url(#'+mode+')'),'vision mode '+mode);
  }
  for(const name of ['protanopia','deuteranopia','tritanopia'])assert($(name).getAttribute('color-interpolation-filters')==='linearRGB','linear RGB simulation '+name);
  for(const button of document.querySelectorAll('button.zoom')){button.click();assert($('zoom').open,'zoom opens');$('close-zoom').click()}
  $('theme').click();assert(document.body.classList.contains('dark'),'dark theme');$('theme').click();
  const fileInput=$('import-file');
  const importText=async text=>{Object.defineProperty(fileInput,'files',{configurable:true,value:[new File([text],'palette.json',{type:'application/json'})]});await fileInput.onchange(new Event('change'))};
  const incoming={version:1,colors:['#123456','#456789','#789ABC','#ABCDEF','#FEDCBA'],stages:{'ability.time.b':{'20000':'#AA5500'}}};
  await importText(JSON.stringify(incoming));
  assert(hex('tier-1').value==='#123456'&&hex('stage-20000').value==='#AA5500','valid JSON imports tiers and threshold overrides');
  await importText('{bad');assert($('error').textContent.includes('导入失败')&&hex('tier-1').value==='#123456','invalid JSON leaves the previous settings active');
  await importText(' '.repeat(65537));assert($('error').textContent.includes('64 KiB'),'oversized import is rejected');
  await importText(JSON.stringify(incoming));
  const click=HTMLAnchorElement.prototype.click;let download;
  HTMLAnchorElement.prototype.click=function(){download={url:this.href,name:this.download}};
  $('export').click();HTMLAnchorElement.prototype.click=click;
  const exported=await (await fetch(download.url)).json();
  assert(download.name==='medal-palette.json'&&JSON.stringify(exported)===JSON.stringify(incoming),'JSON download contains the current full configuration');
  incoming.colors=['#111111','#111111','#111111','#111111','#111111'];
  await importText(JSON.stringify(incoming));assert($('palette-health').textContent.includes('相同颜色'),'duplicate custom colors get a readable notice');
  assert([...document.querySelectorAll('#stages small')].every(el=>el.textContent.includes('色档')),'non-color score labels remain visible');
  $('reset').click();change(hex('tier-1'),'#456789');
  assert($('storage-status').textContent.includes('保存在此浏览器'),'successful save status');
  sessionStorage.setItem(key,JSON.stringify(checks));location.reload();
 }catch(error){sessionStorage.removeItem(key);finish({passed:false,error:String(error),checks})}
})();
</script>`;
    writeFileSync(join(root, '.browser-check.html'), app.replace('</body>', () => check + '</body>'));
    console.log('Prepared local browser verification page.');
}
