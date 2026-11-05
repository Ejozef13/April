# Three.js runtime dependency

Pinned upstream: three 0.170.0 from the npm package. MIT license is included
in THREE-LICENSE.txt and the module header. No runtime CDN is used.

three.module.js is the official three.module.min.js browser artifact, retained
under a stable local filename. GLTFLoader.js and BufferGeometryUtils.js are
upstream addon sources; only imports were adjusted to relative local paths.
The application-specific renderer lives separately in ../avatar3d.js.

Vendor files are identified as third-party code in .gitattributes; they are
not APRIL-authored implementation or model-training work.
