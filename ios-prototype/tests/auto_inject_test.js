/*
Auto-inject test helper for Calcu.html
Usage (in Safari Web Inspector console on the app's WebView):
  1) Paste the contents of this file into Console, or load it as a Snippet and run.
  2) Call `runFullTest({count:200, checkAfterMs:2000})` and await the Promise.

What it does:
  - Inserts `count` synthetic images by dispatching `pencilImage` events.
  - Waits for `checkAfterMs` and then reads IndexedDB to report count/total bytes and whether eviction occurred.
  - Returns a result object for automated assertions.
*/

(async function(){
  // safe-guard: only define once
  if(window.__calcuAutoTest) return;
  window.__calcuAutoTest = {
    async insertTestImages(count=50, delayMs=25, width=1024, height=768){
      for(let i=0;i<count;i++){
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = `hsl(${(i*37)%360} 70% 60%)`;
        ctx.fillRect(0,0,canvas.width,canvas.height);
        ctx.fillStyle = '#222'; ctx.font='48px sans-serif'; ctx.fillText(`Auto ${i+1}`, 40, 120);
        const dataUrl = canvas.toDataURL('image/png');
        window.dispatchEvent(new CustomEvent('pencilImage', { detail: dataUrl }));
        await new Promise(r=>setTimeout(r, delayMs));
      }
      return true;
    },

    async readIndexedDBSummary(){
      function openDB(){
        return new Promise((resolve,reject)=>{
          const req = indexedDB.open('CalcuDrawings');
          req.onsuccess = e => resolve(e.target.result);
          req.onerror = e => reject(e.target.error);
        });
      }
      function toArray(store){
        return new Promise((resolve,reject)=>{
          const out=[]; const req = store.openCursor();
          req.onsuccess = e => { const cur = e.target.result; if(cur){ out.push(cur.value); cur.continue(); } else resolve(out); };
          req.onerror = e => reject(e.target.error);
        });
      }
      try{
        const db = await openDB();
        const tx = db.transaction('images','readonly');
        const store = tx.objectStore('images');
        const arr = await toArray(store);
        const totalBytes = arr.reduce((s,i)=>s + (i.size||0), 0);
        return { count: arr.length, totalBytes, latest: arr[arr.length-1] || null };
      }catch(err){ console.warn('readIndexedDBSummary failed', err); return {error: err.message}; }
    },

    async runFullTest({count=200, delayMs=30, checkAfterMs=2000} = {}){
      const before = await this.readIndexedDBSummary();
      await this.insertTestImages(count, delayMs);
      await new Promise(r=>setTimeout(r, checkAfterMs));
      const after = await this.readIndexedDBSummary();
      return { before, after };
    },

    // Navigate to a URL, ensure test handlers are injected, then run the test on that origin
    async runAgainstUrl(url, {count=200, delayMs=30, checkAfterMs=2000} = {}){
      // navigate
      window.location.href = url;
      // wait for load
      await new Promise((resolve,reject)=>{
        const onLoad = () => { window.removeEventListener('load', onLoad); resolve(); };
        window.addEventListener('load', onLoad);
        // fallback timeout
        setTimeout(resolve, 8000);
      });

      // inject a small helper into the remote page if it doesn't already have the storage listener
      const injected = document.createElement('script');
      injected.textContent = `
        if(!window.__calcuInjectedStorage){
          window.__calcuInjectedStorage = true;
          const DB_NAME = 'CalcuDrawings';
          const DB_VERSION = 1;
          const STORE_NAME = 'images';
          function openDB(){return new Promise((res,rej)=>{const r=indexedDB.open(DB_NAME,DB_VERSION);r.onupgradeneeded=(e)=>{const db=e.target.result;if(!db.objectStoreNames.contains(STORE_NAME)){db.createObjectStore(STORE_NAME,{keyPath:'id',autoIncrement:true});}};r.onsuccess=e=>res(e.target.result);r.onerror=e=>rej(e.target.error)});}
          async function saveImageDataUrl(d){try{const b=(function(dataURL){const parts=dataURL.split(',');const meta=parts[0];const base64=parts[1];const mime=(meta.match(/:(.*?);/)||[,'image/png'])[1];const bin=atob(base64);const len=bin.length;const u8=new Uint8Array(len);for(let i=0;i<len;i++)u8[i]=bin.charCodeAt(i);return new Blob([u8],{type:mime})})(d);
            const db=await openDB();await new Promise((res,rej)=>{const tx=db.transaction(STORE_NAME,'readwrite');const st=tx.objectStore(STORE_NAME);const it={blob:b,timestamp:Date.now(),size:b.size};const rq=st.add(it);rq.onsuccess=()=>res();rq.onerror=(e)=>rej(e.target.error);});}catch(e){console.warn('saveImageDataUrl failed',e);}}
          window.addEventListener('pencilImage', e=>{ if(e && e.detail) saveImageDataUrl(e.detail); });
        }
      `;
      document.documentElement.appendChild(injected);
      // give time for injection to take effect
      await new Promise(r=>setTimeout(r, 400));

      // run the test on the remote page
      const before = await this.readIndexedDBSummary();
      // insert images in the remote page context
      await this.insertTestImages(count, delayMs);
      await new Promise(r=>setTimeout(r, checkAfterMs));
      const after = await this.readIndexedDBSummary();
      return { before, after };
    }
  };
})();
