const vscode = require('vscode');
const path = require('path');
const os = require('os');
const fs = require('fs');

function selected(document) {
  if (!document || document.uri.scheme !== 'file' || document.languageId !== 'python')
    throw new Error('Open a saved Python file first.');
  const configured=vscode.workspace.getConfiguration('april').get('approvedRoot');
  const root=fs.realpathSync(configured || path.join(os.homedir(),'Documents','aprilfiles'));
  const relative=path.relative(root,fs.realpathSync(document.uri.fsPath));
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative))
    throw new Error('This file is outside the approved aprilfiles root.');
  if(document.isDirty)throw new Error('Save the file before reviewing its actual disk contents.');
  return relative.split(path.sep).join('/');
}

function endpoint() {
  const url=new URL(vscode.workspace.getConfiguration('april').get('serverUrl') || 'http://127.0.0.1:8765');
  if(url.protocol!=='http:' || !['localhost','127.0.0.1','[::1]'].includes(url.hostname) ||
     url.username || url.password || url.search || url.hash || url.pathname!=='/')
    throw new Error('Use a loopback APRIL endpoint or local tunnel.');
  return url;
}

function activate(context) {
  const diagnostics=vscode.languages.createDiagnosticCollection('april');
  context.subscriptions.push(diagnostics);
  async function check(document=vscode.window.activeTextEditor?.document) {
    const file=selected(document);
    const response=await fetch(new URL('/api/debug/check',endpoint()),{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({file}),signal:AbortSignal.timeout(5000)
    });
    if(!response.ok)throw new Error('Start APRIL and check its approved folder configuration.');
    const result=await response.json();
    diagnostics.set(document.uri,result.diagnostics.map(item=>{
      const line=Math.min(document.lineCount-1,Math.max(0,item.line-1));
      const column=Math.max(0,item.column-1);
      return new vscode.Diagnostic(new vscode.Range(line,column,line,column+1),item.message,vscode.DiagnosticSeverity.Error);
    }));
  }
  function command(name, callback) {
    context.subscriptions.push(vscode.commands.registerCommand(name,async()=>{
      try{await callback();}catch(error){vscode.window.showErrorMessage('APRIL: '+error.message);}
    }));
  }
  command('april.checkSyntax',()=>check());
  command('april.reviewFile',async()=>{
    const file=selected(vscode.window.activeTextEditor?.document);
    await check();
    const url=endpoint();
    url.searchParams.set('panel','debug');url.searchParams.set('reviewFile',file);
    await vscode.env.openExternal(vscode.Uri.parse(url.href));
  });
  command('april.debugInIDE',async()=>{
    const document=vscode.window.activeTextEditor?.document;
    selected(document);
    if(!vscode.extensions.getExtension('ms-python.debugpy'))
      throw new Error('Install the Python Debugger extension to use IDE execution.');
    const answer=await vscode.window.showWarningMessage(
      'Run '+document.uri.fsPath+' in your IDE? This uses normal desktop permissions, not APRIL’s restricted container.',
      {modal:true},'Run this file');
    if(answer!=='Run this file')return;
    await vscode.debug.startDebugging(vscode.workspace.getWorkspaceFolder(document.uri),{
      name:'APRIL approved Python run',type:'debugpy',request:'launch',
      program:fs.realpathSync(document.uri.fsPath),console:'internalConsole',justMyCode:true
    });
  });
  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(document=>{
    if(!vscode.workspace.getConfiguration('april').get('checkOnSave'))return;
    check(document).catch(()=>{}); // Optional on-save failures never run a program.
  }));
}
module.exports={activate};
