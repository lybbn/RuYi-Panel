var e=Object.defineProperty,l=Object.getOwnPropertySymbols,a=Object.prototype.hasOwnProperty,t=Object.prototype.propertyIsEnumerable,n=(l,a,t)=>a in l?e(l,a,{enumerable:!0,configurable:!0,writable:!0,value:t}):l[a]=t;import{r as s,ag as o,G as i,o as r,H as d,P as u,u as p,J as m,c,a4 as f,O as v,a6 as y,a5 as g,M as h,a as b,L as k,t as _,k as w,aq as x,I as V,n as C,h as j,V as z}from"./@vue.CQt2tj-6.js";import{P as U}from"./Pagination.8Er6hDxx.js";import{_ as D,d as O,i as $,l as q,A as S,j as I,M as A,u as B,e as M,k as F,o as L}from"./index.FQhv3U_5.js";import{b as E}from"./vue-router.BmPBvlxi.js";import{L as P}from"./dialog.Bsrh65Nu.js";import{E as T,a as R}from"./element-plus.C3E-FvSa.js";import{l as G}from"./wslogs.C4YhkFAq.js";import{b as Z}from"./batchOp.C8abNsmc.js";import"./axios.BhTbhqQQ.js";import"./crypto-js.BjUPrIIl.js";import"./@xterm.C7qPmoRH.js";import"./js-cookie.Ch5AnFJE.js";import"./vue-clipboard3.c61pm64N.js";import"./clipboard.BBhAuw9K.js";import"./pinia.CWB7oRTw.js";import"./@element-plus.CU4brdXH.js";import"./nprogress.Dzr5m2b3.js";import"./pinia-plugin-persistedstate.DTf8V5gU.js";import"./destr.ZpApkS-1.js";import"./deep-pick-omit.DP_A4OSP.js";import"./lodash-es.CUM784Py.js";import"./@vueuse.7zPzjEtO.js";import"./@popperjs.DxP-MrnL.js";import"./@ctrl.D-8vaqgC.js";import"./dayjs.BpgH7LzR.js";import"./async-validator.BTKOuuO-.js";import"./memoize-one.Ds0C_khL.js";import"./normalize-wheel-es.BhHBPXsK.js";import"./@floating-ui.D1oRyyfp.js";import"./index.CLtx-Eae.js";import"./vue-codemirror.CkyLiK-7.js";import"./codemirror.Fbop2eii.js";import"./@codemirror.CIOe3mu6.js";import"./@lezer.CQ-BhAmV.js";import"./crelt.DSg10-ms.js";import"./@marijn.Df4efayV.js";import"./style-mod.Dj2YSJ7-.js";import"./w3c-keyname.f-y9tSbI.js";const H={port:{required:!0,trigger:"blur",min:1,max:65535,type:"number",message:"\u7aef\u53e3\u8303\u56f4\u9519\u8bef\uff1a1-65535"},number:{required:!0,trigger:"blur",min:0,type:"number",message:"\u8bf7\u8f93\u5165\u6b63\u786e\u6570\u5b57"},ryportrule:{required:!0,trigger:"blur",validator:function(e,l,a){if(""===l||void 0===l||null==l)a(new Error("\u8bf7\u8f93\u5165\u7aef\u53e3"));else{/^([1-9](\d{0,3}))$|^([1-5]\d{4})$|^(6[0-4]\d{3})$|^(65[0-4]\d{2})$|^(655[0-2]\d)$|^(6553[0-5])$/.test(l)||""===l?a():a(new Error("\u7aef\u53e3\u8303\u56f4\u9519\u8bef\uff1a1-65535"))}}},rypasswordrule:{required:!0,trigger:"blur",validator:function(e,l,a){if(""===l||void 0===l||null==l)a(new Error("\u8bf7\u8f93\u5165\u5bc6\u7801"));else{/^[a-zA-Z0-9]{1}[a-zA-Z0-9_]{0,29}$/.test(l)||""===l?a():a(new Error("\u652f\u6301\u5b57\u6bcd\u3001\u6570\u5b57\u3001_,\u957f\u5ea61-30"))}}},rycomplexpasswordrule:{required:!0,trigger:"blur",validator:function(e,l,a){if(""===l||void 0===l||null==l)a(new Error("\u8bf7\u8f93\u5165\u5bc6\u7801"));else{/^(?![\d]+$)(?![a-zA-Z]+$)(?![^\da-zA-Z]+$).{6,30}$/.test(l)||""===l?a():a(new Error("\u8bf7\u8f93\u5165\u957f\u5ea6\u4e3a 6-30 \u4f4d\u4e14\u5305\u542b\u5b57\u6bcd\u3001\u6570\u5b57\u3001\u7279\u6b8a\u5b57\u7b26\u81f3\u5c11\u4e24\u9879\u7684\u5bc6\u7801\u7ec4\u5408"))}}},rycommonrule:{required:!0,trigger:"blur",validator:function(e,l,a){if(""===l||void 0===l||null==l)a(new Error("\u8bf7\u8f93\u5165\u82f1\u6587\u3001\u6570\u5b57\u3001.-\u548c_,\u957f\u5ea61-60"));else{/^[a-zA-Z0-9]{1}[a-zA-Z0-9._-]{1,60}$/.test(l)||""===l?a():a(new Error("\u8bf7\u8f93\u5165\u82f1\u6587\u3001\u6570\u5b57\u3001.-\u548c_,\u957f\u5ea61-60"))}}}},W={key:5,class:"ryhelp-tips"},J={key:1,class:"ryselectapps"},K={style:{float:"left"}},N={key:0,style:{float:"right","margin-left":"30px",color:"var(--el-text-color-secondary)","font-size":"13px"}},Q={class:"rygc-tips"},X={class:"arttsSettings"},Y={class:"ryhelp-tips"},ee={class:"arttsSettings"},le={class:"ryhelp-tips"},ae=D({__name:"autoInstall",emits:["refreshData","closed"],setup(e,{expose:w,emit:x}){const V=O(),C=x;let j=s(!1),z=s(!1),U=s(!1),D=s(""),B=s(!1),M=s({cpu_count:1,total_memory:1024}),F=s({depend:[],versions:[]}),L=s({appid:"",appname:"",type:"",name:"",version:"",cpu:0,mem:0,advanced:!1,allowport:!1,params:{}}),E=s([]),R=s(null),G=s({name:[{required:!0,message:"\u8bf7\u8f93\u5165\u540d\u79f0",trigger:"blur"}],version:[{required:!0,message:"\u8bf7\u9009\u62e9\u7248\u672c",trigger:"blur"}],params:{}});function Z(){C("closed")}function ae(e){e.preventDefault()}function te(e,l){L.value.params[e]=q("password"==l?15:"text"==l?10:5)}function ne(e){return-1!==["number","select","text","password","checkbox"].indexOf(e)}function se(e,l,a){null!=l&&S.GetsysserviceList({type:e}).then((e=>{2e3==e.code?e.data.length>0&&(L.value.params[l]=e.data[0].value,a.child.services=e.data):I(e.msg)}))}const oe=()=>{R.value.validate((e=>{if(e){U.value=!0;let e=((e,s)=>{for(var o in s||(s={}))a.call(s,o)&&n(e,o,s[o]);if(l)for(var o of l(s))t.call(s,o)&&n(e,o,s[o]);return e})({},L.value);V.loadingInfo.isLoading=!0,V.loadingInfo.content="\u521b\u5efa\u4e2d...",e.action="add",S.DockerSquareAppsMG(e).then((e=>{V.loadingInfo.isLoading=!1,V.loadingInfo.content="",U.value=!1,2e3==e.code?(A(e.msg),Z(),C("refreshData")):I(e.msg)}))}})).catch((e=>{T.error(e)}))};return w({handleOpen:function(e,l){D.value=l,z.value=!0,F.value=$(e),E.value=$(e.formFields),L.value.appid=F.value.appid,L.value.appname=F.value.appname,L.value.type=F.value.type,L.value.name=F.value.appname+"_"+q(5),L.value.version=F.value.versions[0],j.value=!0,E.value.forEach((e=>{G.value.params[e.envkey]=[{required:e.required,trigger:"blur",message:"\u8bf7\u586b\u5199\u5fc5\u586b\u9879"}],e.rule&&G.value.params[e.envkey].push(H[e.rule]);let l=e.random?e.default+q(10):e.default;L.value.params[e.envkey]=l,"selectapps"==e.type&&e.child&&(e.child.services=[],L.value.params[e.child.envkey]=e.child.default,G.value.params[e.child.envkey]=[{required:e.child.required,trigger:"blur",message:"\u8bf7\u586b\u5199\u5fc5\u586b\u9879"}],se(L.value.params[e.envkey],e.child.envkey,e))})),z.value=!0,S.GetDockerContainersLimits().then((e=>{z.value=!1,2e3==e.code?(M.value=e.data,M.value.total_memory=parseInt(M.value.total_memory/1024/1024)):I(e.msg)}))}}),(e,l)=>{const a=o("el-input"),t=o("el-form-item"),n=o("el-col"),s=o("el-option"),w=o("el-select"),x=o("el-button"),V=o("el-checkbox"),C=o("el-tag"),O=o("el-row"),$=o("el-slider"),q=o("el-form");return r(),i(P,{modelValue:p(j),"onUpdate:modelValue":l[6]||(l[6]=e=>_(j)?j.value=e:j=e),title:p(D),width:"50%","before-close":Z,fullscreen:p(B),loading:p(z)},{footer:d((()=>[u(x,{onClick:Z},{default:d((()=>l[12]||(l[12]=[k("\u53d6\u6d88")]))),_:1}),u(x,{type:"primary",onClick:oe,loading:p(U)},{default:d((()=>l[13]||(l[13]=[k("\u786e\u5b9a")]))),_:1},8,["loading"])])),default:d((()=>[u(q,{inline:!1,model:p(L),rules:p(G),ref_key:"rulesForm",ref:R,"label-position":"left","label-width":"auto"},{default:d((()=>[u(O,{gutter:30},{default:d((()=>[u(n,{xs:24,sm:24,md:24,lg:24,xl:12},{default:d((()=>[u(t,{label:"\u540d\u79f0\uff1a",prop:"name"},{default:d((()=>[u(a,{modelValue:p(L).name,"onUpdate:modelValue":l[0]||(l[0]=e=>p(L).name=e),placeholder:"\u8bf7\u8f93\u5165\u540d\u79f0",onKeydown:f(ae,["enter"])},null,8,["modelValue"])])),_:1})])),_:1}),u(n,{xs:24,sm:24,md:24,lg:24,xl:12},{default:d((()=>[u(t,{label:"\u7248\u672c\uff1a",prop:"version"},{default:d((()=>[u(w,{modelValue:p(L).version,"onUpdate:modelValue":l[1]||(l[1]=e=>p(L).version=e),placeholder:"\u8bf7\u9009\u62e9\u5b89\u88c5\u7248\u672c",style:{width:"100%"},filterable:""},{default:d((()=>[(r(!0),c(v,null,y(p(F).versions,(e=>(r(),i(s,{key:e,label:e,value:e},null,8,["label","value"])))),128))])),_:1},8,["modelValue"])])),_:1})])),_:1}),p(E).length>0?(r(!0),c(v,{key:0},y(p(E),((e,o)=>(r(),i(n,{xs:24,sm:24,md:24,lg:24,xl:ne(e.type)?12:24},{default:d((()=>[ne(e.type)?(r(),i(t,{key:0,label:e.label+"\uff1a",prop:"params."+e.envkey},{default:d((()=>["number"==e.type?(r(),i(a,{key:0,type:"number",modelValue:p(L).params[e.envkey],"onUpdate:modelValue":l=>p(L).params[e.envkey]=l,modelModifiers:{number:!0},maxlength:"20"},null,8,["modelValue","onUpdate:modelValue"])):"select"==e.type?(r(),i(w,{key:1,modelValue:p(L).params[e.envkey],"onUpdate:modelValue":l=>p(L).params[e.envkey]=l},{default:d((()=>[(r(!0),c(v,null,y(e.values,(e=>(r(),i(s,{key:e.label,value:e.value,label:e.label},null,8,["value","label"])))),128))])),_:2},1032,["modelValue","onUpdate:modelValue"])):"password"==e.type?(r(),i(a,{key:2,modelValue:p(L).params[e.envkey],"onUpdate:modelValue":l=>p(L).params[e.envkey]=l,modelModifiers:{trim:!0},type:e.type,"show-password":"password"==e.type},g({_:2},[e.random?{name:"append",fn:d((()=>[u(x,{onClick:l=>te(e.envkey,e.type),icon:"refresh"},null,8,["onClick"])])),key:"0"}:void 0]),1032,["modelValue","onUpdate:modelValue","type","show-password"])):"text"==e.type?(r(),i(a,{key:3,modelValue:p(L).params[e.envkey],"onUpdate:modelValue":l=>p(L).params[e.envkey]=l},g({_:2},[e.random?{name:"append",fn:d((()=>[u(x,{onClick:l=>te(e.envkey,e.type),icon:"refresh"},null,8,["onClick"])])),key:"0"}:void 0]),1032,["modelValue","onUpdate:modelValue"])):"checkbox"==e.type?(r(),i(V,{key:4,modelValue:p(L).params[e.envkey],"onUpdate:modelValue":l=>p(L).params[e.envkey]=l,label:e.tips},null,8,["modelValue","onUpdate:modelValue","label"])):m("",!0),e.tips&&"checkbox"!=e.type?(r(),c("span",W,h(e.tips),1)):m("",!0)])),_:2},1032,["label","prop"])):"selectapps"==e.type?(r(),c("div",J,[u(t,{label:e.label+"\uff1a",prop:"params."+e.envkey},{default:d((()=>[u(w,{modelValue:p(L).params[e.envkey],"onUpdate:modelValue":l=>p(L).params[e.envkey]=l,style:{width:"200px"},onChange:l=>se(l,e.child.envkey,e)},{default:d((()=>[(r(!0),c(v,null,y(e.values,(e=>(r(),i(s,{key:e.label,value:e.value,label:e.label},null,8,["value","label"])))),128))])),_:2},1032,["modelValue","onUpdate:modelValue","onChange"])])),_:2},1032,["label","prop"]),u(t,{label:" ","label-width":"5px",prop:"params."+e.child.envkey,class:"norequire",style:{width:"200px"}},{default:d((()=>[e.child?(r(),i(w,{key:0,modelValue:p(L).params[e.child.envkey],"onUpdate:modelValue":l=>p(L).params[e.child.envkey]=l},{default:d((()=>[(r(!0),c(v,null,y(e.child.services,(e=>(r(),i(s,{key:e.label,value:e.value,label:e.label},{default:d((()=>[b("span",K,h(e.label),1),""!=e.from?(r(),c("span",N,["local"===e.from?(r(),i(C,{key:0},{default:d((()=>l[7]||(l[7]=[k(h("\u672c\u5730"))]))),_:1})):"dkapp"===e.from?(r(),i(C,{key:1},{default:d((()=>l[8]||(l[8]=[k(h("\u5bb9\u5668\u5e94\u7528"))]))),_:1})):(r(),i(C,{key:2,type:"success"},{default:d((()=>l[9]||(l[9]=[k(h("\u8fdc\u7a0b"))]))),_:1}))])):m("",!0)])),_:2},1032,["value","label"])))),128))])),_:2},1032,["modelValue","onUpdate:modelValue"])):m("",!0)])),_:2},1032,["prop"]),e.tips?(r(),i(t,{key:0,label:" ","label-width":"5px"},{default:d((()=>[b("span",Q,h(e.tips),1)])),_:2},1024)):m("",!0)])):m("",!0)])),_:2},1032,["xl"])))),256)):m("",!0)])),_:1}),u(t,{label:""},{default:d((()=>[u(V,{modelValue:p(L).advanced,"onUpdate:modelValue":l[2]||(l[2]=e=>p(L).advanced=e),label:"\u9ad8\u7ea7\u914d\u7f6e"},null,8,["modelValue"])])),_:1}),p(L).advanced?(r(),i(O,{key:0,gutter:30},{default:d((()=>[u(n,{xs:24,sm:24,md:24,lg:24,xl:24},{default:d((()=>[u(t,{label:""},{default:d((()=>[u(V,{modelValue:p(L).allowport,"onUpdate:modelValue":l[3]||(l[3]=e=>p(L).allowport=e),label:"\u5141\u8bb8\u5e94\u7528\u7aef\u53e3\u88ab\u5916\u90e8\u8bbf\u95ee\uff08\u653e\u5f00\u9632\u706b\u5899\u7aef\u53e3\uff09"},null,8,["modelValue"])])),_:1})])),_:1}),u(n,{xs:24,sm:24,md:24,lg:24,xl:12},{default:d((()=>[u(t,{label:"CPU\u9650\u5236\uff1a"},{default:d((()=>[b("div",X,[u($,{modelValue:p(L).cpu,"onUpdate:modelValue":l[4]||(l[4]=e=>p(L).cpu=e),"show-input":"","show-stops":"",step:1,min:0,max:p(M).cpu_count,size:"small"},null,8,["modelValue","max"]),l[10]||(l[10]=b("div",{class:"arttsSettings-tips"},"\u6838",-1))]),b("span",Y,"0\u8868\u793a\u5173\u95ed\u9650\u5236\uff0c\u6700\u5927\u53ef\u7528\u4e3a"+h(p(M).cpu_count)+"\u6838",1)])),_:1})])),_:1}),u(n,{xs:24,sm:24,md:24,lg:24,xl:12},{default:d((()=>[u(t,{label:"\u5185\u5b58\u9650\u5236\uff1a"},{default:d((()=>[b("div",ee,[u($,{modelValue:p(L).mem,"onUpdate:modelValue":l[5]||(l[5]=e=>p(L).mem=e),"show-input":"",min:0,max:p(M).total_memory,size:"small"},null,8,["modelValue","max"]),l[11]||(l[11]=b("div",{class:"arttsSettings-tips"},"MB",-1))]),b("span",le,"0\u8868\u793a\u5173\u95ed\u9650\u5236\uff0c\u6700\u5927"+h(p(M).total_memory)+"MB",1)])),_:1})])),_:1})])),_:1})):m("",!0)])),_:1},8,["model","rules"])])),_:1},8,["modelValue","title","fullscreen","loading"])}}},[["__scopeId","data-v-29d72b78"]]),te={class:"rydescriptions"},ne=D({__name:"appDetail",emits:["refreshData","closed"],setup(e,{expose:l,emit:a}){const t=B();O();const n=a;let m=s(!1);s(!1);let f=s("\u5e94\u7528\u8be6\u60c5"),g=s({id:"",appid:"",appname:"",type:"",name:"",version:"",cpu:0,mem:0,advanced:!1,allowport:!1,params:{},appinfo:{formFields:[]}}),x=s([]);function V(){n("closed")}return w((()=>t.ismobile)),l({handleOpen:function(e,l){f.value=l,m.value=!0,g.value=$(e);for(let a in g.value.params)g.value.appinfo.formFields.forEach((e=>{e.envkey==a&&x.value.push({label:e.label,value:g.value.params[a]})}))}}),(e,l)=>{const a=o("el-descriptions-item"),t=o("el-descriptions");return r(),c("div",null,[u(P,{modelValue:p(m),"onUpdate:modelValue":l[0]||(l[0]=e=>_(m)?m.value=e:m=e),title:p(f),width:"60%","before-close":V,class:"containerdialog"},{default:d((()=>[b("div",te,[u(t,{column:1,direction:"horizontal",border:""},{default:d((()=>[u(a,{label:"\u540d\u79f0"},{default:d((()=>[k(h(p(g).name||"-"),1)])),_:1}),u(a,{label:"\u7248\u672c"},{default:d((()=>[k(h(p(g).version||"-"),1)])),_:1}),u(a,{label:"\u6240\u5c5e\u5e94\u7528\u540d"},{default:d((()=>[k(h(p(g).appname||"-"),1)])),_:1}),u(a,{label:"\u6240\u5c5e\u7c7b\u578b"},{default:d((()=>[k(h(p(g).appinfo.typename||"-"),1)])),_:1}),u(a,{label:"\u5b89\u88c5\u8def\u5f84"},{default:d((()=>[k(h(p(g).path||"-"),1)])),_:1}),(r(!0),c(v,null,y(p(x),(e=>(r(),i(a,{label:e.label},{default:d((()=>[k(h(e.value||"-"),1)])),_:2},1032,["label"])))),256)),u(a,{label:"CPU\u9650\u5236"},{default:d((()=>[k(h(p(g).cpu?p(g).cpu:"\u4e0d\u9650\u5236"),1)])),_:1}),u(a,{label:"\u5185\u5b58\u9650\u5236"},{default:d((()=>[k(h(p(g).mem?p(g).mem:"\u4e0d\u9650\u5236"),1)])),_:1}),u(a,{label:"\u5141\u8bb8\u5916\u7f51\u8bbf\u95ee"},{default:d((()=>[k(h(p(g).allowport?"\u662f":"\u5426"),1)])),_:1})])),_:1})])])),_:1},8,["modelValue","title"])])}}},[["__scopeId","data-v-ca7aaa64"]]),se=D({__name:"projectlog",props:{fullscreen:{type:Boolean,default:!1}},emits:["refreshData","closed"],setup(e,{expose:l,emit:a}){const t=a;let n=s(!1),f=s(!1),g=s("\u65e5\u5fd7"),h=s("installlog"),b=s("install"),w=s(!1),j=s({path:"",time:"20m",lines:100,follow:!1}),z=s(""),U=s([{id:"all",name:"\u6240\u6709"},{id:"24h",name:"\u6700\u8fd1\u4e00\u5929"},{id:"5h",name:"\u6700\u8fd15\u5c0f\u65f6"},{id:"1h",name:"\u6700\u8fd11\u5c0f\u65f6"},{id:"20m",name:"\u6700\u8fd120\u5206\u949f"}]),D=s([{id:"all",name:"\u6240\u6709"},{id:1e3,name:1e3},{id:500,name:500},{id:200,name:200},{id:100,name:100}]),O=s(null),$=s(null),q=s("70vh"),S=s(null),I=s(!1),A=s({path:[{required:!0,message:"\u7f3a\u5c11compose\u8def\u5f84",trigger:"blur"}]});function B(){t("closed"),I.value&&t("refreshData")}function M(e){E()}function F(e){z.value="",E()}function L(e){C((()=>{const l=$.value.getRef();if(l.dialogContentRef){const a=l.dialogContentRef.$refs.headerRef.offsetHeight,t=document.body.offsetHeight;q.value=e?t-a-55:"70vh"}}))}function E(){if("installlog"==h.value){let e="runcmd",l="tail -n 30 -f "+(j.value.path+"/dkapp_install.log");"install"!=b.value&&(l="cat "+(j.value.path+"/dkapp_install.log")),S.value.isWebSocketOpen()?(z.value="",S.value.sendMsg({cmd:l},e)):S.value.init("api/wstask/",{cmd:l},e,"")}else O.value.validate((e=>{if(e){f.value=!0;let e="get_compose_log";S.value.isWebSocketOpen()?(z.value="",S.value.sendMsg(j.value,e)):S.value.init("api/wstask/",j.value,e,"")}}))}function T(){f.value=!1}function R(){f.value=!1,I.value=!0}return l({handleOpen:function(e,l){g.value=l,n.value=!0,j.value.path=e.path,b.value=e.status,"install"==e.status?(h.value="installlog",w.value=!0):(h.value="runlog",w.value=!1),C((()=>{E()}))}}),(l,a)=>{const t=o("el-radio-button"),s=o("el-radio-group"),b=o("el-form-item"),C=o("el-option"),I=o("el-select"),E=o("el-form"),Z=x("loading");return r(),i(P,{ref_key:"codeMirrorDialogRef",ref:$,modelValue:p(n),"onUpdate:modelValue":a[4]||(a[4]=e=>_(n)?n.value=e:n=e),title:p(g),width:"60%",top:"45px","before-close":B,class:"pulldialog",fullscreen:e.fullscreen,onOnChangeFullScreen:L},{default:d((()=>[u(E,{inline:!0,model:p(j),rules:p(A),ref_key:"rulesForm",ref:O,"label-position":"right","label-width":"auto",disabled:p(f),class:"filterclass"},{default:d((()=>[u(b,{label:""},{default:d((()=>[u(s,{modelValue:p(h),"onUpdate:modelValue":a[0]||(a[0]=e=>_(h)?h.value=e:h=e),onChange:F},{default:d((()=>[u(t,{label:"\u5b89\u88c5\u65e5\u5fd7",value:"installlog"}),u(t,{label:"\u8fd0\u884c\u65e5\u5fd7",value:"runlog",disabled:p(w)},null,8,["disabled"])])),_:1},8,["modelValue"])])),_:1}),"runlog"==p(h)?(r(),i(b,{key:0,label:"",prop:"time"},{default:d((()=>[u(I,{modelValue:p(j).time,"onUpdate:modelValue":a[1]||(a[1]=e=>p(j).time=e),placeholder:"\u8bf7\u9009\u62e9",style:{width:"100%"},filterable:"",onChange:M},{prefix:d((()=>a[5]||(a[5]=[k(" \u65f6\u95f4 ")]))),default:d((()=>[(r(!0),c(v,null,y(p(U),(e=>(r(),i(C,{key:e.id,label:e.name,value:e.id},null,8,["label","value"])))),128))])),_:1},8,["modelValue"])])),_:1})):m("",!0),"runlog"==p(h)?(r(),i(b,{key:1,label:"",prop:"lines"},{default:d((()=>[u(I,{modelValue:p(j).lines,"onUpdate:modelValue":a[2]||(a[2]=e=>p(j).lines=e),placeholder:"\u8bf7\u9009\u62e9",style:{width:"100%"},filterable:"",onChange:M},{prefix:d((()=>a[6]||(a[6]=[k(" \u6761\u6570 ")]))),default:d((()=>[(r(!0),c(v,null,y(p(D),(e=>(r(),i(C,{key:e.id,label:e.name,value:e.id},null,8,["label","value"])))),128))])),_:1},8,["modelValue"])])),_:1})):m("",!0)])),_:1},8,["model","rules","disabled"]),V(u(G,{modelValue:p(z),"onUpdate:modelValue":a[3]||(a[3]=e=>_(z)?z.value=e:z=e),fontSize:"12px",placeholder:"\u6682\u65e0\u65e5\u5fd7",showLineNums:!1,lineWrapping:!0,mode:"javascript",height:p(q),ref_key:"lyCodemirror",ref:S,onOnerror:T,onOnsuccess:R},null,8,["modelValue","height"]),[[Z,!1]])])),_:1},8,["modelValue","title","fullscreen"])}}},[["__scopeId","data-v-ce2ed896"]]),oe={class:"lyBackupDialog"},ie={key:3},re=D({__name:"backupApps",emits:["refreshData","closed"],setup(e,{expose:l,emit:a}){const t=a;let n=s(!1);s(!1);let m=s("\u6570\u636e\u5e93\u5907\u4efd"),f=s(!1),v=s(!1),y=s(""),g=s({fid:"",type:4,page:1,limit:10}),b=s({page:1,limit:10,total:0}),w=s([]),j=s({});function z(){t("closed"),t("refreshData")}function D(e){g.value.page=e.page,g.value.limit=e.limit,O()}function O(){f.value=!0,S.sysBakBackUpList(g.value).then((e=>{f.value=!1,2e3==e.code?(w.value=e.data.data,b.value.page=e.data.page,b.value.limit=e.data.limit,b.value.total=e.data.total):I(e.msg)}))}function q(){v.value=!0,S.DockerSquareAppsBackup({id:g.value.fid}).then((e=>{v.value=!1,2e3==e.code?(A(e.msg),O()):I(e.msg)}))}let B=s([]),L=s([]);function E(e){L.value=$(e),B.value=e.map((e=>e.id))}let G=s(null);function H(){C((()=>{G.value.handleOpen(null,"\u6279\u91cf\u5220\u9664\u5907\u4efd\u6587\u4ef6")}))}let W=s(0),J=s("0%"),K=s(!1),N=s(1),Q=s("");function X(e){return new Promise((l=>setTimeout(l,e)))}function Y(){return e=this,l=null,a=function*(){N.value=2,K.value=!0,L.value.forEach((e=>{e.status="wait"}));let e=L.value.length,l=0;for(let a=0;a<e;a++){W.value=a+1==e?100:parseInt((a+1)/e*100),J.value=W.value+"%";let t={id:g.value.fid,bid:L.value[a].id};S.DockerSquareAppsDelBak(t).then((e=>{2e3==e.code?L.value[a].status="success":(L.value[a].status="error",l+=1)})),yield X(1e3)}K.value=!1,N.value=3,Q.value=`\u6279\u91cf\u5220\u9664\u5907\u4efd\u6587\u4ef6\u5df2\u5b8c\u6210\uff0c\u5171${e}\u4e2a\u4efb\u52a1\uff0c\u6210\u529f${e-l}\u4e2a\uff0c\u5931\u8d25${l}\u4e2a!`},new Promise(((t,n)=>{var s=e=>{try{i(a.next(e))}catch(l){n(l)}},o=e=>{try{i(a.throw(e))}catch(l){n(l)}},i=e=>e.done?t(e.value):Promise.resolve(e.value).then(s,o);i((a=a.apply(e,l)).next())}));var e,l,a}return l({handleOpen:function(e,l){m.value=l,n.value=!0,g.value.fid=e.id,y.value=e.name,O()}}),(e,l)=>{const a=o("el-button"),t=o("el-form-item"),s=o("el-form"),C=o("el-table-column"),$=o("el-table"),I=o("el-tag"),A=x("loading");return r(),c("div",oe,[u(P,{modelValue:p(n),"onUpdate:modelValue":l[0]||(l[0]=e=>_(n)?n.value=e:n=e),title:p(m),width:"60%","before-close":z,loading:p(v)},{default:d((()=>[u(s,{inline:!1,model:p(g),rules:p(j),ref:"rulesForm","label-position":"right","label-width":"auto",disabled:p(v)},{default:d((()=>[u(t,null,{default:d((()=>[u(a,{type:"primary",onClick:q},{default:d((()=>l[1]||(l[1]=[k("\u5907\u4efd")]))),_:1}),u(a,{onClick:H,disabled:p(B).length<1},{default:d((()=>l[2]||(l[2]=[k("\u5220\u9664")]))),_:1},8,["disabled"])])),_:1})])),_:1},8,["model","rules","disabled"]),V((r(),i($,{ref:"table",border:"",data:p(w),height:410,onSelectionChange:E},{default:d((()=>[u(C,{type:"selection",width:"55",align:"center"}),u(C,{prop:"name",label:"\u540d\u79f0","min-width":"180","show-overflow-tooltip":""}),u(C,{prop:"size",label:"\u5927\u5c0f","min-width":"80"},{default:d((e=>[k(h(p(M)(e.row.size)),1)])),_:1}),u(C,{prop:"filename",label:"\u4f4d\u7f6e","min-width":"190","show-overflow-tooltip":""}),u(C,{prop:"create_at",label:"\u65f6\u95f4","min-width":"170"}),u(C,{prop:"store_type",label:"\u5b58\u50a8\u5bf9\u8c61","min-width":"90"}),u(C,{fixed:"right",label:"\u64cd\u4f5c",width:"160"},{default:d((e=>[u(a,{link:"",type:"primary",onClick:l=>{return a=e.row,void R.confirm(`\u6b64\u64cd\u4f5c\u4f1a\u8986\u76d6\u5f53\u524d\u5e94\u7528\u3010${y.value}\u3011\uff0c\u786e\u5b9a\u8981\u6062\u590d\u5417\uff1f`,"\u63d0\u9192",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((e=>{f.value=!0;let l={id:g.value.fid,bid:a.id};S.DockerSquareAppsRestore(l).then((e=>{f.value=!1,2e3==e.code?(T.success(e.msg),O()):T.warning(e.msg)}))})).catch((()=>{}));var a}},{default:d((()=>l[3]||(l[3]=[k("\u6062\u590d")]))),_:2},1032,["onClick"]),u(a,{link:"",type:"primary",onClick:l=>{return a=e.row,void S.DockerSquareAppsDownloadBak({id:g.value.fid,bid:a.id}).then((e=>{if(null==e?void 0:e.headers)if("application/json"==e.headers["content-type"]){const l=new FileReader;l.readAsText(e.data),l.onload=()=>{const e=JSON.parse(l.result);T.warning(e.msg)}}else F(e.data,a.name);else T.warning("\u54cd\u5e94\u6570\u636e\u683c\u5f0f\u9519\u8bef\uff0c\u8bf7\u68c0\u67e5\u63a5\u53e3\u8fd4\u56de\u6570\u636e\u3002")}));var a}},{default:d((()=>l[4]||(l[4]=[k("\u4e0b\u8f7d")]))),_:2},1032,["onClick"]),u(a,{link:"",type:"primary",onClick:l=>{return a=e.row,void R.confirm(`\u786e\u5b9a\u8981\u5220\u9664\u3010${a.name}\u3011\u5907\u4efd\u6587\u4ef6\u5417\uff1f`,"\u63d0\u9192",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((e=>{f.value=!0;let l={id:g.value.fid,bid:a.id};S.DockerSquareAppsDelBak(l).then((e=>{f.value=!1,2e3==e.code?(T.success(e.msg),O()):T.warning(e.msg)}))})).catch((()=>{}));var a}},{default:d((()=>l[5]||(l[5]=[k("\u5220\u9664")]))),_:2},1032,["onClick"])])),_:1})])),_:1},8,["data"])),[[A,p(f)]]),u(U,{small:!0,"child-msg":p(b),onCallFather:D},null,8,["child-msg"])])),_:1},8,["modelValue","title","loading"]),u(Z,{ref_key:"batchOpRef",ref:G,onClosed:O,tip2:p(Q),percentContent:p(J),percentage:p(W),loadingSave:p(K),stepStatus:p(N)},{table:d((()=>[u($,{data:p(L),border:"","max-height":500},{default:d((()=>[u(C,{prop:"name",label:"\u540d\u79f0","min-width":"280","show-overflow-tooltip":""}),u(C,{prop:"status",label:"\u72b6\u6001","min-width":"100"},{default:d((e=>["wait"==e.row.status?(r(),i(I,{key:0,type:"info"},{default:d((()=>l[6]||(l[6]=[k("\u7b49\u5f85\u5220\u9664")]))),_:1})):"success"==e.row.status?(r(),i(I,{key:1,type:"success"},{default:d((()=>l[7]||(l[7]=[k("\u5220\u9664\u6210\u529f")]))),_:1})):"error"==e.row.status?(r(),i(I,{key:2,type:"danger"},{default:d((()=>l[8]||(l[8]=[k("\u5220\u9664\u5931\u8d25")]))),_:1})):(r(),c("span",ie))])),_:1})])),_:1},8,["data"])])),footer:d((()=>[u(a,{type:"primary",onClick:Y,loading:p(K)},{default:d((()=>l[9]||(l[9]=[k("\u786e\u8ba4")]))),_:1},8,["loading"])])),_:1},8,["tip2","percentContent","percentage","loadingSave","stepStatus"])])}}},[["__scopeId","data-v-5910da64"]]),de={class:"filter-button"},ue={style:{display:"flex","align-items":"center","justify-content":"space-between"}},pe={style:{display:"flex","align-items":"center"}},me={class:"appcard-content"},ce={class:"appcard-header"},fe={class:"appcard-title"},ve={class:"appcard-desc"},ye={class:"appcarddesc-in"},ge={class:"appcard-tag"},he={class:"appcard-content"},be={class:"appcard-header-installed"},ke={class:"appcard-title-installed"},_e={class:"appcard-desc-installed"},we={class:"appcard-install-time"},xe={class:"appcard-tag-installed"},Ve=D({__name:"index",setup(e){const l=E(),a=O(),t=B();w((()=>t.ismobile)),s(!1);let n=s([{name:"\u5168\u90e8",type:"0",sort:0},{name:"\u5df2\u5b89\u88c5",type:"1",sort:0},{name:"\u5efa\u7ad9",type:"10",sort:1},{name:"\u6570\u636e\u5e93",type:"2",sort:2},{name:"\u8fd0\u884c\u73af\u5883",type:"4",sort:3},{name:"\u7cfb\u7edf",type:"18",sort:3}]),g=s({type:"0",page:1,limit:30}),D=s({page:1,limit:30,total:0});let $=s(!1),q=s([]);function I(e){g.value.page=e.page,g.value.limit=e.limit,F()}function A(){S.GetDockerSquareTagsList().then((e=>{if(2e3==e.code&&e.data.length>0){n.value=[{name:"\u5168\u90e8",type:"0",sort:0},{name:"\u5df2\u5b89\u88c5",type:"1",sort:0}];let l=e.data;l.sort(((e,l)=>e.sort-l.sort)),l.forEach((e=>{n.value.push(e)}))}}))}function M(){a.loadingInfo.isLoading=!0,a.loadingInfo.content="\u66f4\u65b0\u5e94\u7528\u5217\u8868\u4e2d...",S.UpdateDockerSquareAppsTags().then((e=>{a.loadingInfo.isLoading=!1,a.loadingInfo.content="",2e3==e.code?(T.success(e.msg),F(),A()):T.warning(e.msg)}))}function F(){$.value=!0,S.GetDockerSquareAppsList(g.value).then((e=>{$.value=!1,2e3==e.code&&(q.value=e.data.data,D.value.page=e.data.page,D.value.limit=e.data.limit,D.value.total=e.data.total)}))}function P(){g.value.page=1,g.value.limit=30,q.value=[],F()}let G=s(!1),Z=s(null);let H=s(!1),W=s(null);let J=s(!1),K=s(null);function N(){g.value.type="1",P()}function Q(e,l){let t="";"start"==l?t="\u542f\u52a8":"stop"==l?t="\u505c\u6b62":"restart"==l?t="\u91cd\u542f":"pause"==l?t="\u6682\u505c":"unpause"==l?t="\u6062\u590d":"remove"==l?t="\u5220\u9664":"reload"==l?t="\u91cd\u8f7d":"rebuild"==l&&(t="\u91cd\u5efa"),R.confirm(`\u786e\u5b9a\u8981\u3010${t}\u3011\u5e94\u7528\u3010${e.name}\u3011\u5417\uff1f`,"\u8b66\u544a",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((n=>{a.loadingInfo.isLoading=!0,a.loadingInfo.content=`${t}\u4e2d...`,S.DockerSquareAppsMG({id:e.id,name:e.name,status:l,action:"set_status"}).then((e=>{a.loadingInfo.isLoading=!1,a.loadingInfo.content="",2e3==e.code?(T.success(e.msg),F()):T.warning(e.msg)}))})).catch((()=>{}))}let X=s(!1),Y=s(null);function ee(e){const l=new Date(e);return l.setHours(l.getHours()+8),l}function le(e,l){const a=ee(e);let t=ee((new Date).toISOString())-a;const n=Math.floor(t/864e5);t-=1e3*n*60*60*24;const s=Math.floor(t/36e5);t-=1e3*s*60*60;const o=Math.floor(t/6e4);t-=1e3*o*60;const i=Math.floor(t/1e3);return n>0?`${n}\u5929`:s>0?`${s}\u5c0f\u65f6`:o>0?`${o}\u5206\u949f`:`${i}\u79d2`}return j((()=>{F(),A()})),(e,t)=>{const s=o("el-button"),w=o("el-input"),j=o("el-col"),O=o("el-row"),S=o("el-card"),A=o("el-empty"),B=o("el-avatar"),E=o("el-tag"),T=o("el-space"),R=o("Loading"),ee=o("el-icon"),te=o("FolderOpened"),oe=o("el-tooltip"),ie=o("Document"),Ve=o("el-main"),Ce=x("loading");return r(),i(Ve,{class:"lycontainer"},{default:d((()=>[u(S,{shadow:"never",header:"\u5206\u7c7b\u7b5b\u9009"},{default:d((()=>[u(O,{style:{"margin-bottom":"15px"}},{default:d((()=>[u(j,{xs:24,sm:20,md:15,lg:8,xl:8},{default:d((()=>[u(w,{modelValue:p(g).searchContent,"onUpdate:modelValue":t[0]||(t[0]=e=>p(g).searchContent=e),clearable:"",placeholder:"\u8bf7\u8f93\u5165\u8981\u641c\u7d22\u7684\u5e94\u7528\u540d\u79f0",onChange:P,onKeyup:f(P,["enter"])},{append:d((()=>[u(s,{onClick:P,icon:"search",class:"search-content"})])),_:1},8,["modelValue"])])),_:1})])),_:1}),b("div",de,[(r(!0),c(v,null,y(p(n),(e=>(r(),i(s,{key:e.value,round:!1,circle:!1,onClick:l=>function(e){q.value=[],g.value.type=e.type,g.value.page=1,g.value.limit=30,F()}(e),type:p(g).type==e.type?"primary":""},{default:d((()=>[k(h(e.name),1)])),_:2},1032,["onClick","type"])))),128))])])),_:1}),u(S,{shadow:"never",header:"\u5e94\u7528\u5217\u8868",style:{"margin-top":"10px"}},{header:d((()=>[b("div",ue,[b("div",pe,[t[5]||(t[5]=b("div",{style:{"margin-right":"15px"}},"\u5e94\u7528\u5217\u8868",-1)),u(s,{icon:"refresh",circle:"",onClick:P,size:"small",style:{"margin-right":"20px"},title:"\u5237\u65b0"}),u(U,{"hide-on-single-page":!0,small:!0,"child-msg":p(D),onCallFather:I,border:!1,position:"right",layout:"prev, pager, next"},null,8,["child-msg"])]),u(s,{onClick:M,size:"small",title:"\u540c\u6b65\u670d\u52a1\u5668\u5e94\u7528\u5217\u8868"},{default:d((()=>t[6]||(t[6]=[k("\u66f4\u65b0\u5217\u8868")]))),_:1})])])),default:d((()=>[p(q).length<1?V((r(),i(A,{key:0,description:"\u6682\u65e0\u6570\u636e"},null,512)),[[Ce,p($)]]):V((r(),i(O,{key:1,gutter:20},{default:d((()=>["1"!=p(g).type?(r(!0),c(v,{key:0},y(p(q),((e,l)=>(r(),i(j,{xs:24,sm:12,md:8,lg:8,xl:8},{default:d((()=>[u(S,{shadow:"hover",class:"appcardbox"},{default:d((()=>[u(O,{gutter:20},{default:d((()=>[u(j,{xs:8,sm:6,md:6,lg:6,xl:5},{default:d((()=>[u(B,{class:"appcard-icon",shape:"square",size:65,src:p(L)(e.icon,"fileicons")},null,8,["src"])])),_:2},1024),u(j,{xs:16,sm:18,md:18,lg:18,xl:19},{default:d((()=>[b("div",me,[b("div",ce,[u(T,{wrap:""},{default:d((()=>[b("span",fe,h(e.title),1),1==e.installed?(r(),i(E,{key:0,type:"success",class:"rymrl-nrem",round:"",size:"small"},{default:d((()=>[t[7]||(t[7]=k(" \u5df2\u5b89\u88c5")),b("span",null,h(e.installedCount)+"\u4e2a",1)])),_:2},1024)):m("",!0)])),_:2},1024),u(s,{class:"appcard-button",type:"primary",disabled:1==e.installed&&!e.multiple,onClick:z((l=>{return a=e,G.value=!0,void C((()=>{Z.value.handleOpen(a,`${a.title}\u5b89\u88c5\u914d\u7f6e`)}));var a}),["stop"])},{default:d((()=>t[8]||(t[8]=[k(" \u5b89\u88c5 ")]))),_:2},1032,["disabled","onClick"])]),b("div",ve,[b("span",ye,h(e.desc),1)]),b("div",ge,[u(E,{class:"rymr-npx"},{default:d((()=>[b("span",null,h(e.typename),1)])),_:2},1024)])])])),_:2},1024)])),_:2},1024)])),_:2},1024)])),_:2},1024)))),256)):(r(!0),c(v,{key:1},y(p(q),((e,n)=>(r(),i(j,{xs:24,sm:12,md:12,lg:12,xl:12,key:n},{default:d((()=>[u(S,{shadow:"hover",class:"appcardbox"},{default:d((()=>[u(O,{gutter:20},{default:d((()=>[u(j,{xs:6,sm:6,md:6,lg:5,xl:3},{default:d((()=>[u(B,{class:"appcard-icon-installed",size:65,shape:"square",src:p(L)(e.icon,"fileicons")},null,8,["src"])])),_:2},1024),u(j,{xs:18,sm:18,md:18,lg:19,xl:21},{default:d((()=>[b("div",he,[b("div",be,[b("div",null,[b("span",ke,h(e.name),1),"running"==e.status?(r(),i(E,{key:0,class:"rymrl-nrem-installed",type:"success",size:"small",round:""},{default:d((()=>t[9]||(t[9]=[k(" \u5df2\u542f\u52a8 ")]))),_:1})):"created"==e.status?(r(),i(E,{key:1,class:"rymrl-nrem-installed",type:"success",size:"small",round:""},{default:d((()=>t[10]||(t[10]=[k(" \u5df2\u521b\u5efa ")]))),_:1})):"install"==e.status?(r(),i(E,{key:2,class:"rymrl-nrem-installed",type:"primary",size:"small",round:""},{default:d((()=>[t[11]||(t[11]=k(" \u521b\u5efa\u4e2d")),u(ee,{class:"lyicon-loading"},{default:d((()=>[u(R)])),_:1})])),_:1})):"restarting"==e.status?(r(),i(E,{key:3,class:"rymrl-nrem-installed",type:"primary",size:"small",round:""},{default:d((()=>[t[12]||(t[12]=k(" \u91cd\u542f\u4e2d")),u(ee,{class:"lyicon-loading"},{default:d((()=>[u(R)])),_:1})])),_:1})):"paused"==e.status?(r(),i(E,{key:4,class:"rymrl-nrem-installed",type:"warning",size:"small",round:""},{default:d((()=>t[13]||(t[13]=[k(" \u5df2\u6682\u505c ")]))),_:1})):"dead"==e.status?(r(),i(E,{key:5,class:"rymrl-nrem-installed",type:"info",size:"small",round:""},{default:d((()=>t[14]||(t[14]=[k(" \u5df2\u7ed3\u675f ")]))),_:1})):"removing"==e.status?(r(),i(E,{key:6,class:"rymrl-nrem-installed",type:"danger",size:"small",round:""},{default:d((()=>[t[15]||(t[15]=k(" \u79fb\u9664\u4e2d")),u(ee,{class:"lyicon-loading"},{default:d((()=>[u(R)])),_:1})])),_:1})):"exited"==e.status?(r(),i(E,{key:7,class:"rymrl-nrem-installed",type:"warning",size:"small",round:""},{default:d((()=>t[16]||(t[16]=[k(" \u5df2\u505c\u6b62 ")]))),_:1})):(r(),i(E,{key:8,type:"info",size:"small",class:"rymrl-nrem-installed",round:""},{default:d((()=>t[17]||(t[17]=[k(" \u672a\u77e5 ")]))),_:1})),b("span",null,[u(oe,{effect:"dark",content:"\u8fdb\u5165\u5b89\u88c5\u76ee\u5f55",placement:"top"},{default:d((()=>[u(s,{type:"primary",plain:"",link:"",onClick:t=>function(e){e.path&&(a.fileInfo.currentDir=e.path,l.push({path:"/files"}))}(e)},{default:d((()=>[u(ee,null,{default:d((()=>[u(te)])),_:1})])),_:2},1032,["onClick"])])),_:2},1024)]),b("span",null,[u(oe,{effect:"dark",content:"\u67e5\u770b\u65e5\u5fd7",placement:"top"},{default:d((()=>[u(s,{type:"primary",plain:"",link:"",onClick:l=>{return a=e,J.value=!0,void C((()=>{K.value.handleOpen(a,`\u3010${a.name}\u3011\u65e5\u5fd7`)}));var a}},{default:d((()=>[u(ee,null,{default:d((()=>[u(ie)])),_:1})])),_:2},1032,["onClick"])])),_:2},1024)])]),u(s,{plain:"",round:"",size:"small",onClick:l=>{return a=e,X.value=!0,void C((()=>{Y.value.handleOpen(a,"\u3010"+a.name+"\u3011\u5907\u4efd")}));var a}},{default:d((()=>t[18]||(t[18]=[k(" \u5907\u4efd ")]))),_:2},1032,["onClick"])]),b("div",_e,[u(s,{class:"rymr-npx",size:"small"},{default:d((()=>[k("\u7248\u672c:"+h(e.version),1)])),_:2},1024),(r(!0),c(v,null,y(e.ports,(e=>(r(),i(s,{class:"rymr-npx installd-opbutton",size:"small"},{default:d((()=>[k("\u7aef\u53e3:"+h(e),1)])),_:2},1024)))),256))]),b("div",we," \u5df2\u5b89\u88c5\uff1a"+h(le(e.create_at)),1),t[25]||(t[25]=b("div",{class:"rydivider"},null,-1)),b("div",xe,[u(s,{size:"small",plain:"",round:"",onClick:l=>Q(e,"stop"),disabled:"exited"==e.status||"install"==e.status},{default:d((()=>t[19]||(t[19]=[k("\u505c\u6b62")]))),_:2},1032,["onClick","disabled"]),u(s,{class:"installd-opbutton",size:"small",plain:"",round:"",onClick:l=>Q(e,"restart"),disabled:"install"==e.status||"restarting"==e.status},{default:d((()=>t[20]||(t[20]=[k("\u91cd\u542f")]))),_:2},1032,["onClick","disabled"]),u(s,{class:"installd-opbutton",size:"small",plain:"",round:"",onClick:l=>Q(e,"start"),disabled:"running"==e.status||"install"==e.status||"restarting"==e.status},{default:d((()=>t[21]||(t[21]=[k("\u542f\u52a8")]))),_:2},1032,["onClick","disabled"]),u(s,{class:"installd-opbutton",size:"small",plain:"",round:"",onClick:l=>Q(e,"rebuild"),disabled:"install"==e.status},{default:d((()=>t[22]||(t[22]=[k("\u91cd\u5efa")]))),_:2},1032,["onClick","disabled"]),u(s,{class:"installd-opbutton",size:"small",plain:"",round:"",onClick:l=>{return a=e,H.value=!0,void C((()=>{W.value.handleOpen(a,`${a.name}\u8be6\u60c5`)}));var a}},{default:d((()=>t[23]||(t[23]=[k("\u8be6\u60c5")]))),_:2},1032,["onClick"]),u(s,{class:"installd-opbutton",size:"small",plain:"",round:"",onClick:l=>Q(e,"remove")},{default:d((()=>t[24]||(t[24]=[k("\u5220\u9664")]))),_:2},1032,["onClick"])])])])),_:2},1024)])),_:2},1024)])),_:2},1024)])),_:2},1024)))),128))])),_:1})),[[Ce,p($)]]),u(U,{small:!0,"child-msg":p(D),onCallFather:I,border:!1,position:"right"},null,8,["child-msg"])])),_:1}),p(G)?(r(),i(ae,{key:0,ref_key:"moduleinstallFlag",ref:Z,onClosed:t[1]||(t[1]=e=>_(G)?G.value=!1:G=!1),onRefreshData:N},null,512)):m("",!0),p(H)?(r(),i(ne,{key:1,ref_key:"appinstallDetailFlag",ref:W,onClosed:t[2]||(t[2]=e=>_(H)?H.value=!1:H=!1)},null,512)):m("",!0),p(J)?(r(),i(se,{key:2,ref_key:"projectlogFlag",ref:K,onClosed:t[3]||(t[3]=e=>_(J)?J.value=!1:J=!1)},null,512)):m("",!0),p(X)?(r(),i(re,{key:3,ref_key:"moduleBackupFlag",ref:Y,onClosed:t[4]||(t[4]=e=>_(X)?X.value=!1:X=!1)},null,512)):m("",!0)])),_:1})}}},[["__scopeId","data-v-baa80227"]]);export{Ve as default};
