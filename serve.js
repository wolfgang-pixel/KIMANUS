const http = require('http');
const fs = require('fs');
const path = require('path');
const dir = __dirname;
const port = 8095;
const mime = {'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.webp':'image/webp','.ico':'image/x-icon','.webmanifest':'application/manifest+json'};
http.createServer((req,res)=>{
  let p = req.url.split('?')[0];
  if(p==='/') p='/index.html';
  const fp = path.join(dir, p);
  const ext = path.extname(fp);
  fs.readFile(fp,(err,data)=>{
    if(err){res.writeHead(404);res.end('Not found');return;}
    res.writeHead(200,{'Content-Type':mime[ext]||'application/octet-stream','Cache-Control':'no-cache'});
    res.end(data);
  });
}).listen(port,()=>console.log('Serving on http://localhost:'+port));
