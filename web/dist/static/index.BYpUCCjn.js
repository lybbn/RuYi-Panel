var e=Object.defineProperty,l=Object.getOwnPropertySymbols,a=Object.prototype.hasOwnProperty,t=Object.prototype.propertyIsEnumerable,o=(l,a,t)=>a in l?e(l,a,{enumerable:!0,configurable:!0,writable:!0,value:t}):l[a]=t;import{r as i,ag as s,c as r,o as n,P as d,H as u,u as p,O as c,a6 as m,I as f,G as v,a as y,M as w,Q as g,J as h,L as _,t as k,k as b,h as j,aq as x,a4 as C,n as I}from"./@vue.CQt2tj-6.js";import{_ as O,i as L,A as W,d as S,u as V,o as z,m as D}from"./index.FQhv3U_5.js";import{P}from"./Pagination.8Er6hDxx.js";import{L as F}from"./dialog.Bsrh65Nu.js";import{E as q,a as M}from"./element-plus.C3E-FvSa.js";import{i as R}from"./installLog.XAeeFQ3u.js";import{b as B}from"./vue-router.BmPBvlxi.js";import{s as E}from"./softInfo.kcMLyEqL.js";import"./axios.BhTbhqQQ.js";import"./crypto-js.BjUPrIIl.js";import"./@xterm.C7qPmoRH.js";import"./js-cookie.Ch5AnFJE.js";import"./vue-clipboard3.c61pm64N.js";import"./clipboard.BBhAuw9K.js";import"./pinia.CWB7oRTw.js";import"./@element-plus.CU4brdXH.js";import"./nprogress.Dzr5m2b3.js";import"./pinia-plugin-persistedstate.DTf8V5gU.js";import"./destr.ZpApkS-1.js";import"./deep-pick-omit.DP_A4OSP.js";import"./lodash-es.CUM784Py.js";import"./@vueuse.7zPzjEtO.js";import"./@popperjs.DxP-MrnL.js";import"./@ctrl.D-8vaqgC.js";import"./dayjs.BpgH7LzR.js";import"./async-validator.BTKOuuO-.js";import"./memoize-one.Ds0C_khL.js";import"./normalize-wheel-es.BhHBPXsK.js";import"./@floating-ui.D1oRyyfp.js";import"./index.CLtx-Eae.js";import"./vue-codemirror.CkyLiK-7.js";import"./codemirror.Fbop2eii.js";import"./@codemirror.CIOe3mu6.js";import"./@lezer.CQ-BhAmV.js";import"./crelt.DSg10-ms.js";import"./@marijn.Df4efayV.js";import"./style-mod.Dj2YSJ7-.js";import"./w3c-keyname.f-y9tSbI.js";const T={style:{float:"left"}},U={style:{float:"right",color:"var(--el-text-color-secondary)","font-size":"13px"}},$={class:"ry-cj-title"},A={class:"ry-cj-desc"},G={key:0,class:"ry-sp-tips"},H={key:1,class:"ry-sp-tips"},J={class:"ry-cj-care"},K={key:0},Q=O({__name:"moduleInstall",emits:["refreshData","closed"],setup(e,{expose:b,emit:j}){const x=j;let C=i(!1),I=i(!1),O=i("\u8be6\u60c5"),S=i({id:"",name:"",version_id:1}),V={},z=i([]),D=i(!1),P=i({});function M(){x("closed")}function R(){return!D.value&&"mysql"==S.value.name}let B=i(null);function E(e=1){B.value.validate((i=>{if(i){I.value=!0;let i=((e,i)=>{for(var s in i||(i={}))a.call(i,s)&&o(e,s,i[s]);if(l)for(var s of l(i))t.call(i,s)&&o(e,s,i[s]);return e})({},S.value);i.action="install",i.type=e,W.sysSoftManage(i).then((e=>{I.value=!1,2e3==e.code?(M(),x("refreshData",e.data.id,S.value.name)):q.warning(e.msg)}))}}))}return b({handleOpen:function(e,l){O.value=l,C.value=!0,e&&(V=L(e),S.value.id=V.id,S.value.name=V.name,z.value=V.versions,D.value=V.is_windows)}}),(e,l)=>{const a=s("el-option"),t=s("el-select"),o=s("el-form-item"),i=s("el-button"),b=s("el-col"),j=s("el-divider"),x=s("Warning"),L=s("el-icon"),W=s("el-text"),q=s("el-row"),Q=s("el-form");return n(),r("div",null,[d(F,{modelValue:p(C),"onUpdate:modelValue":l[3]||(l[3]=e=>k(C)?C.value=e:C=e),title:p(O),width:"50%","before-close":M},{default:u((()=>[d(Q,{inline:!1,model:p(S),rules:p(P),ref_key:"rulesForm",ref:B,"label-position":"right","label-width":"auto"},{default:u((()=>[d(q,{gutter:20},{default:u((()=>[d(b,{span:24,style:{display:"flex"}},{default:u((()=>[d(o,{label:"",prop:"version_id",style:{"margin-right":"15px"}},{default:u((()=>[d(t,{modelValue:p(S).version_id,"onUpdate:modelValue":l[0]||(l[0]=e=>p(S).version_id=e),placeholder:"\u8bf7\u9009\u62e9",style:{width:"240px"}},{default:u((()=>[(n(!0),r(c,null,m(p(z),(e=>f((n(),v(a,{key:e.id,label:p(V).name+" "+e.version,value:e.id},{default:u((()=>[y("span",T,w(p(V).name+" "+e.version),1),y("span",U,w(e.c_version),1)])),_:2},1032,["label","value"])),[[g,!e.hide]]))),128))])),_:1},8,["modelValue"])])),_:1}),d(o,{label:"",prop:""},{default:u((()=>[d(i,{type:"primary",onClick:l[1]||(l[1]=e=>E(1)),disabled:p(I)},{default:u((()=>l[4]||(l[4]=[_("\u5b89\u88c5")]))),_:1},8,["disabled"]),R?(n(),v(i,{key:0,type:"primary",onClick:l[2]||(l[2]=e=>E(2))},{default:u((()=>l[5]||(l[5]=[_("\u5feb\u901f\u5b89\u88c5")]))),_:1})):h("",!0)])),_:1})])),_:1}),d(j),d(b,{span:24},{default:u((()=>[y("div",$,[d(L,{size:"22"},{default:u((()=>[d(x)])),_:1}),l[6]||(l[6]=y("h1",null,"\u5e94\u7528\u8bf4\u660e",-1))]),y("div",A,[d(W,null,{default:u((()=>[_(w(p(V).desc),1)])),_:1})]),"docker"==p(V).name&&p(D)?(n(),r("div",G,l[7]||(l[7]=[_(" \u7279\u522b\u63d0\u793a\uff1aWindows\u4e0b\u5b89\u88c5docker\uff0c\u9700\u5148\u5b89\u88c5Windows\u7684WSL\u529f\u80fd(\u9ed8\u8ba4\u81ea\u52a8\u5b89\u88c5)\uff0c"),y("span",{style:{color:"red"}},"\u4f46\u9700\u91cd\u542fWindows\u540e\u624d\u80fd\u6b63\u5e38\u4f7f\u7528",-1),y("div",{class:"ry-cj-care"},[y("li",{style:{color:"green"}},"\u8bf7\u624b\u52a8\u5b89\u88c5\u7cfb\u7edfWSL(\u9700win10\u53ca\u4ee5\u4e0a\u7cfb\u7edf)"),y("li",{style:{color:"green"}},"\u624b\u52a8\u5b89\u88c5\u65b9\u6cd5\uff1a\u63a7\u5236\u9762\u677f=>\u7a0b\u5e8f\u548c\u529f\u80fd=>\u542f\u7528\u6216\u5173\u95edWindows\u529f\u80fd ,\u7136\u540e\u52fe\u9009\u4ee5\u4e0b2\u4e2a\u5b89\u88c5"),y("li",{style:{color:"black"}},"1\u3001\u9002\u7528\u4e8eLinux\u7684Windows\u5b50\u7cfb\u7edf"),y("li",{style:{color:"black"}},"2\u3001\u865a\u62df\u673a\u5e73\u53f0"),y("li",{style:{color:"black"}},"\u6700\u540e\u3010\u91cd\u542fWindows\u7cfb\u7edf\u3011")],-1)]))):h("",!0),"go"==p(V).name?(n(),r("div",H," \u7279\u522b\u63d0\u793a\uff1a\u5982\u679c\u5b89\u88c5\u4e86\u591a\u4e2a\u7248\u672c\u7684"+w(p(V).name)+"\uff0c\u9ed8\u8ba4\u65b0\u5b89\u88c5\u7684"+w(p(V).name)+"\u4e3a\u9ed8\u8ba4\u7248\u672c\uff0c\u60f3\u5207\u6362\uff0c\u70b9\u51fb\u3010\u8bbe\u7f6e\u3011\u5207\u6362\u4e3a\u60f3\u8981\u7684\u7248\u672c\u5373\u53ef ",1)):h("",!0),y("div",J,[l[8]||(l[8]=y("li",null,"\u8bf7\u5148\u786e\u4fdd\u5728\u5b89\u88c5\u6b64\u5e94\u7528\u524d\uff0c\u5df2\u624b\u52a8\u5b89\u88c5\u597d\u6b64\u5e94\u7528\u6240\u9700\u7684\u73af\u5883\uff01",-1)),l[9]||(l[9]=y("li",null,"\u5982\u679c\u5df2\u5b58\u5728\u6b64\u5e94\u7528\u6216\u76ee\u5f55\u6587\u4ef6\uff0c\u5b89\u88c5\u65f6\u4f1a\u8986\u76d6\u539f\u6587\u4ef6\uff01",-1)),l[10]||(l[10]=y("li",null,"\u5b89\u88c5\u5e94\u7528\u4e3a\u8017\u65f6\u64cd\u4f5c\uff0c\u8bf7\u8010\u5fc3\u7b49\u5f85\u5b89\u88c5\u5b8c\u6bd5\uff01",-1)),R?(n(),r("li",K,"linux\u73af\u5883\u4e0b\u5b89\u88c5\u5e94\u7528\uff0c\u9009\u62e9\u3010\u7f16\u8bd1\u5b89\u88c5\u3011\u4f1a\u66f4\u8017\u65f6,\u3010\u5feb\u901f\u5b89\u88c5\u3011\u5b89\u88c5\u66f4\u5feb\uff01")):h("",!0)])])),_:1})])),_:1})])),_:1},8,["model","rules"])])),_:1},8,["modelValue","title"])])}}},[["__scopeId","data-v-cc418eb8"]]),N={class:"filter-button"},X={style:{display:"flex","align-items":"center"}},Y={style:{display:"flex","align-items":"center"}},Z={key:0,class:"ryellipsis"},ee={key:1},le={key:2},ae={key:0,class:"lyczj"},te=["onClick"],oe={key:1},ie={key:3},se=O({__name:"index",setup(e){const l=B(),a=S(),t=V();let o=b((()=>t.ismobile)),g=i(!1),O=i([{label:"\u5168\u90e8",value:"0",icon:"",type:"primary"},{label:"\u5df2\u5b89\u88c5",value:"1",icon:"",type:"success"},{label:"\u6570\u636e\u5e93",value:"2",icon:"",type:"success"},{label:"Web\u670d\u52a1\u5668",value:"3",icon:"",type:"success"},{label:"\u8fd0\u884c\u73af\u5883",value:"4",icon:"",type:"danger"},{label:"\u5b89\u5168\u9632\u62a4",value:"5",icon:"",type:"danger"}]),L=i({type:"0",page:1,limit:10}),F=i({page:1,limit:10,total:0});let T=i(!1),U=i([]);function $(e){L.value.page=e.page,L.value.limit=e.limit,A()}function A(){T.value=!0,W.sysSoftList(L.value).then((e=>{T.value=!1,2e3==e.code&&(g.value=e.data.is_windows,U.value=e.data.soft.list,F.value.page=e.data.soft.page,F.value.limit=e.data.soft.limit,F.value.total=e.data.soft.total)}))}function G(e){if(e.installed&&e.version){let l="";for(let a=0;a<e.versions.length;a++)if(e.version===e.versions[a].c_version&&"openresty"==e.versions[a].version){l=` ${e.versions[a].version} `;break}return l}return""}function H(){L.value.type="0",L.value.page=1,L.value.limit=10,A()}let J=i(!1),K=i(null);let se=i(!1),re=i(null);function ne(e,l){a.getSystemTaskIngInfo(),se.value=!0,I((()=>{let a={id:e};re.value.handleOpen(a,"\u5b89\u88c5\u3010"+l+"\u3011\u65e5\u5fd7\u8be6\u60c5")}))}function de(){window.location.reload()}let ue=i(!1),pe=i(null);function ce(e){"supervisor"==e.name?l.push({path:"/tools",query:{tabs:"supervisor"}}):"docker"==e.name?l.push({path:"/dockers/settings"}):(ue.value=!0,I((()=>{pe.value.handleOpen(e,"\u3010"+e.name+"("+e.version+")\u3011\u7ba1\u7406")})))}function me(e){U.value.forEach((l=>{l.id==e.id&&(l.status=e.status)}))}return j((()=>{A()})),(e,t)=>{const i=s("el-button"),b=s("el-input"),j=s("el-col"),S=s("el-row"),V=s("el-card"),B=s("el-image"),fe=s("el-tag"),ve=s("el-table-column"),ye=s("el-tooltip"),we=s("el-table"),ge=s("el-main"),he=x("loading");return n(),v(ge,{class:"lycontainer"},{default:u((()=>[d(V,{shadow:"never",header:"\u5206\u7c7b\u7b5b\u9009"},{default:u((()=>[d(S,{style:{"margin-bottom":"15px"}},{default:u((()=>[d(j,{xs:24,sm:20,md:15,lg:8,xl:8},{default:u((()=>[d(b,{modelValue:p(L).searchContent,"onUpdate:modelValue":t[0]||(t[0]=e=>p(L).searchContent=e),clearable:"",placeholder:"\u8bf7\u8f93\u5165\u8981\u641c\u7d22\u7684\u5e94\u7528\u540d\u79f0",onChange:H,onKeyup:C(H,["enter"])},{append:u((()=>[d(i,{onClick:H,icon:"search",class:"search-content"})])),_:1},8,["modelValue"])])),_:1})])),_:1}),y("div",N,[(n(!0),r(c,null,m(p(O),(e=>(n(),v(i,{key:e.value,round:!1,circle:!1,icon:e.icon?e.icon:"",onClick:l=>function(e){L.value.type=e.value,L.value.page=1,L.value.limit=10,A()}(e),type:p(L).type===e.value?"primary":""},{default:u((()=>[_(w(e.label),1)])),_:2},1032,["icon","onClick","type"])))),128))])])),_:1}),d(V,{shadow:"never",header:"\u5e94\u7528\u5217\u8868",style:{"margin-top":"10px"}},{header:u((()=>[y("div",X,[t[4]||(t[4]=y("div",{style:{"margin-right":"15px"}},"\u5e94\u7528\u5217\u8868",-1)),d(i,{icon:"refresh",circle:"",onClick:H,size:"small"})])])),default:u((()=>[f((n(),v(we,{data:p(U),style:{width:"100%","border-top":"1px solid var(--el-border-color-lighter)"},"header-cell-class-name":"table-header-style"},{default:u((()=>[d(ve,{prop:"title",label:"\u8f6f\u4ef6\u540d\u79f0","min-width":"180","show-overflow-tooltip":""},{default:u((e=>[y("div",Y,[d(B,{src:p(z)(e.row.icon,"fileicons"),style:{width:"25px",height:"25px","margin-right":"5px"}},null,8,["src"]),"nginx"==e.row.name?(n(),r("div",Z,w(e.row.installed?e.row.title+G(e.row)+e.row.version:e.row.title),1)):"python"==e.row.name||"go"==e.row.name?(n(),r("div",ee,[_(w(e.row.title)+" ",1),"go"==e.row.name&&e.row.is_default?(n(),v(fe,{key:0,type:"primary",effect:"light",round:"",size:"small"},{default:u((()=>t[5]||(t[5]=[_("\u9ed8\u8ba4")]))),_:1})):h("",!0)])):(n(),r("div",le,w(e.row.installed?e.row.title+e.row.version:e.row.title),1))])])),_:1}),d(ve,{prop:"desc",label:"\u8bf4\u660e","min-width":"300","show-overflow-tooltip":""}),d(ve,{prop:"price",label:"\u7c7b\u578b",width:"115"},{default:u((e=>[y("span",null,w(0==e.row.price?"\u514d\u8d39":e.row.price.toString()+"\u5143/\u5e74"),1)])),_:1}),d(ve,{prop:"typename",label:"\u5206\u7c7b",width:"130"},{default:u((e=>[d(fe,null,{default:u((()=>[_(w(e.row.typename),1)])),_:2},1024)])),_:1}),d(ve,{label:"\u4f4d\u7f6e",width:"80"},{default:u((e=>[e.row.installed?(n(),r("div",ae,[d(ye,{effect:"dark",content:"\u70b9\u51fb\u6253\u5f00\u5b89\u88c5\u76ee\u5f55",placement:"bottom"},{default:u((()=>[y("img",{class:"ruyi-fileicons",src:D,onClick:t=>{var o;(o=e.row).install_path&&(a.fileInfo.currentDir=o.install_path,l.push({path:"/files"}))}},null,8,te)])),_:2},1024)])):(n(),r("span",oe))])),_:1}),d(ve,{prop:"status",label:"\u72b6\u6001",width:"112"},{default:u((e=>[e.row.installed&&e.row.status&&4==e.row.type&&"docker"!=e.row.name?(n(),v(fe,{key:0,type:"success"},{default:u((()=>t[6]||(t[6]=[_("\u5df2\u5b89\u88c5")]))),_:1})):e.row.installed&&e.row.status?(n(),v(fe,{key:1,type:"success"},{default:u((()=>t[7]||(t[7]=[_("\u5df2\u542f\u52a8")]))),_:1})):e.row.installed&&!e.row.status?(n(),v(fe,{key:2,type:"danger"},{default:u((()=>t[8]||(t[8]=[_("\u5df2\u505c\u6b62")]))),_:1})):(n(),r("span",ie))])),_:1}),d(ve,{fixed:!p(o)&&"right",label:"\u64cd\u4f5c",width:"150"},{default:u((e=>[e.row.installed?h("",!0):(n(),v(i,{key:0,link:"",type:"primary",onClick:l=>{return a=e.row,J.value=!0,void I((()=>{let e={desc:a.desc,is_windows:g.value,versions:a.versions,name:a.name,title:a.title,id:a.id};K.value.handleOpen(e,a.title)}));var a}},{default:u((()=>t[9]||(t[9]=[_("\u5b89\u88c5")]))),_:2},1032,["onClick"])),e.row.installed&&"python"!=e.row.name?(n(),v(i,{key:1,link:"",type:"primary",onClick:l=>ce(e.row)},{default:u((()=>t[10]||(t[10]=[_("\u8bbe\u7f6e")]))),_:2},1032,["onClick"])):h("",!0),e.row.installed?(n(),v(i,{key:2,link:"",type:"primary",onClick:l=>{return t=e.row,void M.confirm(`\u786e\u5b9a\u8981\u5378\u8f7d\u3010${t.name+" "+t.version}\u3011\u5417\uff1f`,"\u8b66\u544a",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a\u5378\u8f7d",type:"warning"}).then((e=>{a.loadingInfo.isLoading=!0,a.loadingInfo.content="\u6b63\u5728\u5378\u8f7d\u4e2d...";let l={action:"uninstall",id:t.id};W.sysSoftManage(l).then((e=>{a.loadingInfo.isLoading=!1,a.loadingInfo.content="",2e3==e.code?(q.success(e.msg),A()):q.warning(e.msg)}))})).catch((()=>{}));var t}},{default:u((()=>t[11]||(t[11]=[_("\u5378\u8f7d")]))),_:2},1032,["onClick"])):h("",!0)])),_:1},8,["fixed"])])),_:1},8,["data"])),[[he,p(T)]]),d(P,{small:!0,"child-msg":p(F),onCallFather:$,border:!1,position:"right"},null,8,["child-msg"])])),_:1}),p(se)?(n(),v(R,{key:0,ref_key:"moduleinstallLogFlag",ref:re,onClosed:t[1]||(t[1]=e=>k(se)?se.value=!1:se=!1),onRefreshData:de},null,512)):h("",!0),p(J)?(n(),v(Q,{key:1,ref_key:"moduleInstallFlag",ref:K,onClosed:t[2]||(t[2]=e=>k(J)?J.value=!1:J=!1),onRefreshData:ne},null,512)):h("",!0),p(ue)?(n(),v(E,{key:2,ref_key:"softInfoFlag",ref:pe,onClosed:t[3]||(t[3]=e=>k(ue)?ue.value=!1:ue=!1),onRefreshData:A,onRefreshStatus:me},null,512)):h("",!0)])),_:1})}}},[["__scopeId","data-v-87cbc7af"]]);export{se as default};
