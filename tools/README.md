# Editable 3D April

`april-approved.blend` is Enrique's edited model, saved with Blender 5.2.
`../april/web/assets/april-prototype.glb` is its app-ready export and remains the
runtime default. The GLB filename stays the same so existing local settings load the new
design without migration. The original `april-prototype.blend` remains untouched
so pulling this update preserves local edits to that older working file. Use Blender 5.2 or newer for the source file.

The edited geometry began with our original procedural cartoon terrier. The
uploaded Tripo showcase MP4 was only a visual reference; its original mesh,
texture, watermark and frames were not extracted into this model.

The approved export preserves the edited geometry and transforms, attaches both ears to
HeadPivot, removes unused duplicate pivots and brings Tongue forward below the
edited muzzle. TailPivot and runtime tongue visibility remain compatible with
the existing app. Tail wagging, idle breathing and tongue state changes are
app-driven; they are not baked Blender timeline clips. Preserve HeadPivot,
TailPivot and Tongue names and parenting during future edits.

Open the current design:

```bash
blender tools/april-approved.blend
```

Save a separate working copy before editing. Export GLB with cameras/lights off
and no baked animation clips to preserve the app-driven prototype animations.

To regenerate the **original procedural base**, rather than overwrite the
approved design:

```bash
blender -b --python tools/build_april_model.py
```

This now writes `tools/april-procedural.blend`,
`april/web/assets/april-procedural.glb` and `/tmp/april-procedural.png`.
It does not overwrite the approved runtime model. Future fully rigged models
can use clips named idle, listening, transcribing, thinking, speaking and error;
the renderer supports these separately. Reduced motion is respected.

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
