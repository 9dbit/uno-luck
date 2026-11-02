'use strict';
const $=id=>document.getElementById(id);
const ruleset=null;
function say(message){$('admin-status').textContent=message;}
function paragraph(parent,text){const p=document.createElement('p');p.textContent=text;parent.append(p);return p;}
function modalButton(parent,text,fn){const b=document.createElement('button');b.textContent=text;b.type='button';b.addEventListener('click',fn);parent.append(b);return b;}
function modal(title){$('modal-title').textContent=title;$('modal-content').replaceChildren();if(!$('modal').open)$('modal').showModal();return $('modal-content');}
function closeModal(){if($('modal').open)$('modal').close();window.UNOLuckSoundStudio?.stopPreview();}
async function unlockAudio(){const ok=await window.UNOLuckSound?.unlock();if(ok)window.UNOLuckSound.setEnabled(true);return Boolean(ok);}
function showCelebrationGallery(){
  const area=modal('Galeri Celebration · Demo Visual');
  paragraph(area,'Pilih efek untuk melihat animasi dan mendengar suara. Mode demo tidak mengubah hasil kartu, saldo, atau riwayat.');
  for(let rank=1;rank<=5;rank++){
    const item=window.UNOLuckCelebration?.registry[rank];
    if(!item)continue;
    modalButton(area,`PERINGKAT ${rank} · ${item.name} · ${item.multiplier}×`,async()=>{
      closeModal();await unlockAudio();window.UNOLuckCelebration.present(null,{preview:true,rank});
    });
    const rule=ruleset?.celebrations?.find(t=>t.rank===rank)?.rule;
    if(rule)paragraph(area,'Kombinasi: '+rule);
  }
}
async function testSound(){
  closeModal();
  const ok=await unlockAudio();
  if(!ok){say('Audio belum aktif. Sentuh Main dengan Suara lalu coba lagi.');return;}
  const heard=await window.UNOLuckSound?.testSound();
  say(heard?'Tes audio diputar. Pastikan volume media iPhone aktif.':`Audio gagal: ${window.UNOLuckSound?.lastError||'coba sentuh MAIN DENGAN SUARA'}`);
}
function showSoundVolume(){
  const area=modal('Audio Mixer · UNO LUCK');
  paragraph(area,'Master, Musik dan SFX mengikuti pengaturan Sound Cloud yang dipublikasikan. Admin dapat mengubah di desktop dan perubahan akan tersinkron. Volume fisik iPhone tetap mengikuti iOS.');
  for(const [title,property,setter] of [
    ['MASTER','masterVolume','setMasterVolume'],
    ['MUSIC','musicVolume','setMusicVolume'],
    ['SFX','volume','setVolume']]){
    const label=paragraph(area,title+' · '+Math.round((window.UNOLuckSound?.[property]??0)*100)+'%');
    const input=document.createElement('input');
    input.type='range';input.min='0';input.max='100';input.step='5';
    input.value=String(Math.round((window.UNOLuckSound?.[property]??0)*100));
    input.setAttribute('aria-label',title+' Volume');
    input.addEventListener('input',()=>{
      const n=Number(input.value);
      window.UNOLuckSound?.[setter](n/100);
      label.textContent=title+' · '+n+'%';
      if(title==='SFX'&&n>0)window.UNOLuckSound?.setEnabled(true);
      window.UNOLuckSoundStudio?.schedulePublishMixer?.();
    });
    area.append(input);
  }
  modalButton(area,'TES AUDIO',async()=>{
    const ok=await unlockAudio();
    if(!ok){say('Audio belum aktif: '+(window.UNOLuckSound?.lastError||'periksa volume perangkat'));return;}
    const heard=await window.UNOLuckSound.testSound();
    say(heard?'Tes fanfare diputar. Jika senyap, naikkan volume media iPhone.':
      'Tes audio gagal: '+(window.UNOLuckSound?.lastError||'periksa status audio'));
  });
}
function showSoundStudio(){
  const area=modal('SOUND STUDIO · CUSTOM EFFECTS');
  if(window.UNOLuckSoundStudio)window.UNOLuckSoundStudio.show(area);
  else paragraph(area,'Sound Studio belum tersedia. Refresh halaman.');
}

$('admin-studio').addEventListener('click',showSoundStudio);
$('admin-mixer').addEventListener('click',showSoundVolume);
$('admin-test-sound').addEventListener('click',testSound);
$('admin-gallery').addEventListener('click',showCelebrationGallery);
$('modal-close').addEventListener('click',closeModal);
$('modal').addEventListener('click',e=>{if(e.target===$('modal'))closeModal();});
$('modal').addEventListener('close',()=>window.UNOLuckSoundStudio?.stopPreview());
