var e=Object.defineProperty,l=Object.getOwnPropertySymbols,a=Object.prototype.hasOwnProperty,t=Object.prototype.propertyIsEnumerable,o=(l,a,t)=>a in l?e(l,a,{enumerable:!0,configurable:!0,writable:!0,value:t}):l[a]=t,n=(e,n)=>{for(var i in n||(n={}))a.call(n,i)&&o(e,i,n[i]);if(l)for(var i of l(n))t.call(n,i)&&o(e,i,n[i]);return e};import{r as i,ag as r,c as s,o as d,P as u,H as p,u as m,G as c,J as f,a as g,L as v,M as h,t as b,k as y,h as _,aq as j,I as w,a4 as k,O as x,a6 as V,n as C}from"./@vue.CQt2tj-6.js";import{_ as I,A as O,M as D,j as M,d as z,u as L,m as P,p as R}from"./index.FQhv3U_5.js";import{P as U}from"./Pagination.8Er6hDxx.js";import{L as A}from"./dialog.Bsrh65Nu.js";import"./crypto-js.BjUPrIIl.js";import"./js-cookie.Ch5AnFJE.js";import"./clipboard.BBhAuw9K.js";import{b as B}from"./vue-router.BmPBvlxi.js";import{a as T,E as q}from"./element-plus.C3E-FvSa.js";import"./axios.BhTbhqQQ.js";import"./vue-clipboard3.c61pm64N.js";import"./pinia.CWB7oRTw.js";import"./@element-plus.CU4brdXH.js";import"./nprogress.Dzr5m2b3.js";import"./@xterm.C7qPmoRH.js";import"./pinia-plugin-persistedstate.DTf8V5gU.js";import"./destr.ZpApkS-1.js";import"./deep-pick-omit.DP_A4OSP.js";import"./lodash-es.CUM784Py.js";import"./@vueuse.7zPzjEtO.js";import"./@popperjs.DxP-MrnL.js";import"./@ctrl.D-8vaqgC.js";import"./dayjs.BpgH7LzR.js";import"./async-validator.BTKOuuO-.js";import"./memoize-one.Ds0C_khL.js";import"./normalize-wheel-es.BhHBPXsK.js";import"./@floating-ui.D1oRyyfp.js";const F={style:{display:"flex","align-items":"center",width:"100%"}},E={style:{width:"150px","padding-left":"20px"}},G=I({__name:"moduleAdd",emits:["refreshData","closed"],setup(e,{expose:l,emit:a}){const t=a;let o=i(!1),y=i(!1),_=i("\u6dfb\u52a0\u5b58\u50a8\u5377"),j=i({name:"",advanced:!1,driver:"local",driver_opts:"",labels:""}),w=i({name:[{required:!0,message:"\u8bf7\u8f93\u5165\u5b58\u50a8\u5377\u540d\u79f0",trigger:"blur"}]});function k(){t("closed")}let x=i(null);function V(){x.value.validate((e=>{if(e){y.value=!0;let e=n({},j.value);e.action="add",O.DockerVolumesMg(e).then((e=>{y.value=!1,2e3==e.code?(D(e.msg),k(),t("refreshData")):M(e.msg)}))}}))}return l({handleOpen:function(e,l){_.value=l,o.value=!0}}),(e,l)=>{const a=r("el-input"),t=r("el-checkbox"),n=r("el-form-item"),i=r("el-tag"),C=r("el-form"),I=r("el-button");return d(),s("div",null,[u(A,{modelValue:m(o),"onUpdate:modelValue":l[4]||(l[4]=e=>b(o)?o.value=e:o=e),title:m(_),width:"680px","before-close":k},{footer:p((()=>[u(I,{onClick:k,loading:m(y)},{default:p((()=>l[5]||(l[5]=[v("\u53d6\u6d88")]))),_:1},8,["loading"]),u(I,{type:"primary",onClick:V,loading:m(y)},{default:p((()=>l[6]||(l[6]=[v("\u4fdd\u5b58")]))),_:1},8,["loading"])])),default:p((()=>[u(C,{inline:!1,model:m(j),rules:m(w),ref_key:"rulesForm",ref:x,"label-position":"right","label-width":"auto"},{default:p((()=>[u(n,{label:"\u540d\u79f0\uff1a",prop:"name"},{default:p((()=>[g("div",F,[u(a,{clearable:"",placeholder:"\u8bf7\u8f93\u5165\u5b58\u50a8\u5377\u540d\u79f0",modelValue:m(j).name,"onUpdate:modelValue":l[0]||(l[0]=e=>m(j).name=e),modelModifiers:{trim:!0}},null,8,["modelValue"]),g("div",E,[u(t,{modelValue:m(j).advanced,"onUpdate:modelValue":l[1]||(l[1]=e=>m(j).advanced=e),label:"\u66f4\u591a\u914d\u7f6e"},null,8,["modelValue"])])])])),_:1}),m(j).advanced?(d(),c(n,{key:0,label:"\u8bbe\u5907\uff1a",prop:"driver"},{default:p((()=>[u(i,null,{default:p((()=>[v(h(m(j).driver),1)])),_:1})])),_:1})):f("",!0),m(j).advanced?(d(),c(n,{key:1,label:"\u9009\u9879\uff1a",prop:"driver_opts"},{default:p((()=>[u(a,{modelValue:m(j).driver_opts,"onUpdate:modelValue":l[2]||(l[2]=e=>m(j).driver_opts=e),type:"textarea",autosize:{minRows:3,maxRows:5},placeholder:"\u4e00\u884c\u4e00\u4e2a\nkey1=value1\nkey2=value2"},null,8,["modelValue"])])),_:1})):f("",!0),m(j).advanced?(d(),c(n,{key:2,label:"\u6807\u7b7e\uff1a",prop:"labels"},{default:p((()=>[u(a,{modelValue:m(j).labels,"onUpdate:modelValue":l[3]||(l[3]=e=>m(j).labels=e),type:"textarea",autosize:{minRows:3,maxRows:5},placeholder:"\u4e00\u884c\u4e00\u4e2a\nkey1=value1\nkey2=value2"},null,8,["modelValue"])])),_:1})):f("",!0)])),_:1},8,["model","rules"])])),_:1},8,["modelValue","title"])])}}},[["__scopeId","data-v-32bc6103"]]),S={class:"handle-top"},$={class:"search-sites-input"},H={class:"lyczj"},J=["onClick"],K={style:{display:"flex",gap:"5px"}},N={key:0},Q=I({__name:"index",setup(e,{expose:l}){const a=B(),t=z(),o=L();let I=y((()=>o.ismobile)),D=i(!1),M=i(null),A=i(!1),F=i({page:1,limit:10}),E=i({page:1,limit:10,total:0}),Q=i([]);function W(e){F.value.page=e.page,F.value.limit=e.limit,X()}function X(){D.value=!0;let e=n({},F.value);O.GetDockerVolumes(e).then((e=>{D.value=!1,2e3===e.code&&(Q.value=e.data.data,E.value.page=e.data.page,E.value.limit=e.data.limit,E.value.total=e.data.total)}))}function Y(){F.value.page=1,X()}function Z(){A.value=!0,C((()=>{M.value.handleOpen(null,"\u6dfb\u52a0\u5b58\u50a8\u5377")}))}function ee(){T.confirm("\u786e\u5b9a\u8981\u6e05\u7406\u6ca1\u6709\u4f7f\u7528\u7684\u5b58\u50a8\u5377\u5417\uff1f\u5220\u9664\u540e\u65e0\u6cd5\u6062\u590d\uff01\uff01\uff01","\u8b66\u544a",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((e=>{t.loadingInfo.isLoading=!0,t.loadingInfo.content="\u6e05\u7406\u4e2d...",O.DockerVolumesMg({action:"prune"}).then((e=>{t.loadingInfo.isLoading=!1,t.loadingInfo.content="",2e3==e.code?(q.success(e.msg),Y()):q.warning(e.msg)}))})).catch((()=>{}))}return l({RefreshData:function(){C((()=>{X()}))}}),_((()=>{X()})),(e,l)=>{const o=r("el-button"),n=r("el-col"),i=r("el-input"),y=r("el-row"),_=r("el-table-column"),C=r("el-tooltip"),z=r("el-tag"),L=r("el-table"),B=j("loading");return d(),s("div",null,[g("div",S,[u(y,null,{default:p((()=>[u(n,{xs:24,sm:16,md:16,lg:16,xl:16},{default:p((()=>[u(o,{type:"primary",onClick:Z,icon:"plus"},{default:p((()=>l[5]||(l[5]=[v("\u6dfb\u52a0\u5b58\u50a8\u5377")]))),_:1}),u(o,{type:"danger",onClick:ee,icon:"delete",plain:""},{default:p((()=>l[6]||(l[6]=[v("\u6e05\u7406\u5b58\u50a8\u5377")]))),_:1}),u(o,{icon:"refresh",circle:"",onClick:Y,style:{"margin-left":"10px"}})])),_:1}),u(n,{xs:24,sm:8,md:8,lg:8,xl:8},{default:p((()=>[g("div",$,[u(i,{modelValue:m(F).search,"onUpdate:modelValue":l[0]||(l[0]=e=>m(F).search=e),clearable:"",onClear:l[1]||(l[1]=e=>Y()),"suffix-icon":"Search",onKeyup:l[2]||(l[2]=k((e=>Y()),["enter"])),onChange:l[3]||(l[3]=e=>Y()),placeholder:"\u641c\u7d22"},null,8,["modelValue"])])])),_:1})])),_:1})]),w((d(),c(L,{data:m(Q),style:{width:"100%","border-top":"1px solid var(--el-border-color-lighter)"},"header-cell-class-name":"table-header-style"},{default:p((()=>[u(_,{prop:"name",label:"\u540d\u79f0","min-width":"175","show-overflow-tooltip":""}),u(_,{prop:"mountpoint",label:"\u6302\u8f7d\u70b9",width:"130"},{default:p((({row:e})=>[g("div",H,[u(C,{effect:"dark",content:e.mountpoint,placement:"top"},{default:p((()=>[g("img",{class:"ruyi-fileicons",src:P,onClick:l=>{var o;(o=e.mountpoint)&&(t.fileInfo.currentDir=o,a.push({path:"/files"}))}},null,8,J)])),_:2},1032,["content"])])])),_:1}),u(_,{prop:"containers",label:"\u4f7f\u7528\u5bb9\u5668","min-width":"150"},{default:p((({row:e})=>[(d(!0),s(x,null,V(e.containers,(e=>(d(),s("div",K,[u(z,{size:"small",effect:"plain",type:"primary"},{default:p((()=>[v(h(e),1)])),_:2},1024)])))),256))])),_:1}),u(_,{prop:"driver",label:"\u8bbe\u5907",width:"130"},{default:p((({row:e})=>[u(z,null,{default:p((()=>[v(h(e.driver),1)])),_:2},1024)])),_:1}),u(_,{prop:"labels",label:"\u6807\u7b7e","min-width":"130"},{default:p((({row:e})=>[(d(!0),s(x,null,V(e.labels,((e,l)=>(d(),s("div",null,[u(z,{type:"info"},{default:p((()=>[v(h(l)+" ",1),""!=e?(d(),s("span",N,h("="+e),1)):f("",!0)])),_:2},1024)])))),256))])),_:1}),u(_,{prop:"created",label:"\u521b\u5efa\u65f6\u95f4","min-width":"170"},{default:p((e=>[g("span",null,h(m(R)(e.row.created)),1)])),_:1}),u(_,{fixed:!m(I)&&"right",label:"\u64cd\u4f5c",width:"130"},{default:p((e=>[u(o,{link:"",type:"primary",onClick:l=>{return a=e.row,void T.confirm(`\u786e\u5b9a\u8981\u5220\u9664\u3010${a.name}\u3011\u5b58\u50a8\u5377\u5417\uff1f`,"\u8b66\u544a",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((e=>{t.loadingInfo.isLoading=!0,t.loadingInfo.content="\u5220\u9664\u4e2d...",O.DockerVolumesMg({id:a.id,name:a.name,action:"delete"}).then((e=>{t.loadingInfo.isLoading=!1,t.loadingInfo.content="",2e3==e.code?(q.success(e.msg),X()):q.warning(e.msg)}))})).catch((()=>{}));var a}},{default:p((()=>l[7]||(l[7]=[v("\u5220\u9664")]))),_:2},1032,["onClick"])])),_:1},8,["fixed"])])),_:1},8,["data"])),[[B,m(D)]]),u(U,{small:!0,"child-msg":m(E),onCallFather:W,border:!1,position:"right"},null,8,["child-msg"]),m(A)?(d(),c(G,{key:0,ref_key:"moduleAddFlag",ref:M,onRefreshData:X,onClosed:l[4]||(l[4]=e=>b(A)?A.value=!1:A=!1)},null,512)):f("",!0)])}}},[["__scopeId","data-v-7af10201"]]);export{Q as default};
