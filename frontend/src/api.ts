export async function api<T=any>(url:string,body?:unknown,method?:string):Promise<T>{
 const response=await fetch('/api'+url,{method:method||(body===undefined?'GET':'POST'),headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await response.json(); if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data)); return data;
}
export async function copy(text:string){
 if(navigator.clipboard){try{await navigator.clipboard.writeText(text);return;}catch{}}
 const el=document.createElement('textarea');el.value=text;document.body.appendChild(el);el.select();const ok=document.execCommand('copy');el.remove();if(!ok)throw new Error('Буфер обмена недоступен. Сохраните текст в файл.');
}
export function download(name:string,text:string,type='text/plain;charset=utf-8'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
export const uid=()=>crypto.randomUUID();
export const signed=(value:number)=>value>=0?'+'+value:String(value);
export const statusLabel:Record<string,string>={valid:'Готово',available:'Доступно',missing:'Нужно выбрать',invalid:'Недействительно',review:'Нужна проверка',inactive:'Неактивно',ready:'Готова',idle:'Ожидание',loading:'Загрузка',parsing:'Разбор страниц',paused:'Приостановлено',incomplete:'Не завершена',error:'Ошибка'};
