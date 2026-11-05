import * as THREE from './vendor/three.module.js';
import {GLTFLoader} from './vendor/GLTFLoader.js';

export async function mountAvatar(container, url, onClick) {
  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(32,1,.1,100);
  camera.position.set(2.8,1.8,-3.4); camera.lookAt(0,1,0);
  const renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
  renderer.setClearColor(0,0);
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  container.append(renderer.domElement);
  renderer.domElement.setAttribute('aria-label','April 3D prototype; click to show controls');
  renderer.domElement.setAttribute('role','button');renderer.domElement.tabIndex=0;
  renderer.domElement.onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();onClick();}};
  renderer.domElement.onclick=onClick;
  scene.add(new THREE.HemisphereLight(0xf8fff1,0x3d493a,2.8));
  const key=new THREE.DirectionalLight(0xffe7cb,3);key.position.set(3,5,-3);scene.add(key);
  const gltf=await new GLTFLoader().loadAsync(url);
  const dog=gltf.scene;scene.add(dog);
  const raycaster=new THREE.Raycaster(), pointer=new THREE.Vector2();
  renderer.domElement.onclick=event=>{
    const rect=renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
    raycaster.setFromCamera(pointer,camera);
    if(raycaster.intersectObject(dog,true).length)onClick();
  };
  const ring=new THREE.Mesh(new THREE.TorusGeometry(.85,.018,8,64),
                            new THREE.MeshBasicMaterial({color:0x8fc462,transparent:true,opacity:.75}));
  ring.rotation.x=Math.PI/2;ring.position.y=.04;scene.add(ring);
  const colors={idle:0x8fc462,listening:0xccff66,transcribing:0x70d5e8,thinking:0xffcb70,speaking:0xbd9aff,error:0xff6868};
  const tail=dog.getObjectByName('TailPivot'), head=dog.getObjectByName('HeadPivot'), tongue=dog.getObjectByName('Tongue');
  const clips=new THREE.AnimationMixer(dog);
  const actions=new Map(gltf.animations.map(clip=>[clip.name.toLowerCase(),clips.clipAction(clip)]));
  const resize=new ResizeObserver(()=>{
    const {width,height}=container.getBoundingClientRect();
    renderer.setSize(width,Math.max(height,1),false);camera.aspect=width/Math.max(height,1);camera.updateProjectionMatrix();
  });resize.observe(container);
  let last=0, previous='', active=null, frame;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function draw(now) {
    frame=requestAnimationFrame(draw);
    if (now-last<40 || document.hidden) return; // At most 25fps; no hidden-page animation work.
    const delta=Math.min((now-last)/1000,.1);last=now;
    const state=document.body.dataset.state || 'idle';
    if (state!==previous) {
      ring.material.color.setHex(colors[state]||colors.idle);
      renderer.domElement.title='April: '+state+' · click for controls';
      active?.fadeOut(.2);
      active=actions.get(state)||actions.get('idle');
      active?.reset().fadeIn(.2).play();previous=state;
    }
    const t=now/1000, moving=!reduced.matches;
    if (gltf.animations.length && moving) clips.update(delta);
    else {
      dog.position.y=moving?Math.sin(t*1.8)*.012:0;
      if(tail)tail.rotation.z=moving&&(state==='speaking'||document.body.classList.contains('input-active'))?Math.sin(t*22)*.45:0;
      if(head)head.rotation.z=moving&&state==='listening'?-.12:0;
      if(tongue)tongue.visible=['listening','thinking','speaking'].includes(state);
    }
    renderer.render(scene,camera);
    container.dataset.rendered="true";
  }
  frame=requestAnimationFrame(draw);
  return ()=>{
    cancelAnimationFrame(frame);resize.disconnect();
    scene.traverse(object=>{
      object.geometry?.dispose();
      const materials=object.material?(Array.isArray(object.material)?object.material:[object.material]):[];
      for(const material of materials){for(const value of Object.values(material))if(value?.isTexture)value.dispose();material.dispose();}
    });
    renderer.dispose();container.replaceChildren();
  };
}
