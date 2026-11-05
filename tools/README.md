# Editable 3D prototype

`april-prototype.blend` and `../april/web/assets/april-prototype.glb` are original
procedural cartoon geometry created by `build_april_model.py`. The uploaded
Tripo showcase MP4 was inspected as a proportions/color reference; no mesh,
texture, watermark or video frame was extracted into this asset.

Rebuild with Blender (no Python pip dependencies required):

```bash
blender -b --python tools/build_april_model.py
```

This also writes a transparent still to `/tmp/april-3d-prototype.png`.
The source provides named HeadPivot, TailPivot and Tongue objects. The local
renderer uses these for simple state animation. It can instead play GLB
animation clips named idle, listening, transcribing, thinking, speaking and error.
Reduced motion is respected. This is a prototype, not a reconstruction of the
video's original model.

To replace: create/export your own GLB into `april/web/assets/`, then set
`avatar_model_url = "/static/assets/your-model.glb"` in ignored local settings.
Keep custom personal assets out of Git unless you intend to publish them.
The current prototype is standing; the camera expects +Y forward in Blender,
Z up, approximately two Blender units tall.

Recommended free/open-source authoring tools:
- [Blender](https://www.blender.org/): complete modeling, sculpting, rigging,
  animation and GLB export. Best path for a finished personal April.
- [Blockbench](https://www.blockbench.net/): approachable low-poly browser/desktop
  editor, GPL-3.0 source at JannisX11/blockbench. Good for a stylized first model.
- [SculptGL](https://stephaneginier.com/sculptgl/): MIT browser sculpting tool,
  source at stephomi/sculptgl. Useful for sculpting; use Blender for rigging and
  final animation.

Tripo is the source of the supplied showcase, not an open-source authoring tool
we are bundling. An MP4 does not contain editable GLB geometry. If you later
export the actual asset, inspect its license/format before importing it.

Renderer dependency: Three.js 0.170.0, MIT, vendored locally with its license in
`april/web/vendor/THREE-LICENSE.txt`; no runtime CDN. Original upstream module
imports were changed to relative local paths. Blender is only a build/edit tool;
users do not need Blender installed to display the already exported GLB.
