var e=Object.defineProperty,o=Object.getOwnPropertySymbols,l=Object.prototype.hasOwnProperty,a=Object.prototype.propertyIsEnumerable,t=(o,l,a)=>l in o?e(o,l,{enumerable:!0,configurable:!0,writable:!0,value:a}):o[l]=a,n=(e,n)=>{for(var i in n||(n={}))l.call(n,i)&&t(e,i,n[i]);if(o)for(var i of o(n))a.call(n,i)&&t(e,i,n[i]);return e};import{r as i,ag as r,c as d,o as s,P as u,H as c,u as p,O as f,a6 as g,G as m,L as _,t as h,k as v,i as j,h as y,aq as b,J as k,a as w,M as V,D as I,I as x,a4 as C,n as L}from"./@vue.CQt2tj-6.js";import{d as S,i as U,A as $,_ as q,T as P}from"./index.FQhv3U_5.js";import{l as O}from"./index.CLtx-Eae.js";import{l as M}from"./fileList.CCYZ4jbj.js";import{L as T}from"./dialog.Bsrh65Nu.js";import{E as D,a as B}from"./element-plus.C3E-FvSa.js";import"./axios.BhTbhqQQ.js";import"./crypto-js.BjUPrIIl.js";import"./@xterm.C7qPmoRH.js";import"./js-cookie.Ch5AnFJE.js";import"./vue-clipboard3.c61pm64N.js";import"./clipboard.BBhAuw9K.js";import"./pinia.CWB7oRTw.js";import"./@element-plus.CU4brdXH.js";import"./vue-router.BmPBvlxi.js";import"./nprogress.Dzr5m2b3.js";import"./pinia-plugin-persistedstate.DTf8V5gU.js";import"./destr.ZpApkS-1.js";import"./deep-pick-omit.DP_A4OSP.js";import"./lodash-es.CUM784Py.js";import"./@vueuse.7zPzjEtO.js";import"./@popperjs.DxP-MrnL.js";import"./@ctrl.D-8vaqgC.js";import"./dayjs.BpgH7LzR.js";import"./async-validator.BTKOuuO-.js";import"./memoize-one.Ds0C_khL.js";import"./normalize-wheel-es.BhHBPXsK.js";import"./@floating-ui.D1oRyyfp.js";import"./vue-codemirror.CkyLiK-7.js";import"./codemirror.Fbop2eii.js";import"./@codemirror.CIOe3mu6.js";import"./@lezer.CQ-BhAmV.js";import"./crelt.DSg10-ms.js";import"./@marijn.Df4efayV.js";import"./style-mod.Dj2YSJ7-.js";import"./w3c-keyname.f-y9tSbI.js";import"./Pagination.8Er6hDxx.js";const F={__name:"moduleInstallPipPkg",emits:["refreshData","closed"],setup(e,{expose:o,emit:l}){const a=l,t=S();let v=i(!1),j=i(!1),y=i("\u4f9d\u8d56\u5b89\u88c5"),b=i({id:"",name:"",version:"",sourcename:"\u963f\u91cc\u4e91"}),k=i([{version:"\u963f\u91cc\u4e91"},{version:"\u534e\u4e3a\u4e91"},{version:"\u6e05\u534e\u5927\u5b66"}]),w=i({name:[{required:!0,message:"\u8bf7\u8f93\u5165\u5e93\u540d\u79f0",trigger:"blur"}]});function V(){a("closed")}let I=i(null);function x(){I.value.validate((e=>{if(e){t.loadingInfo.isLoading=!0,t.loadingInfo.content="\u5b89\u88c5\u4e2d...";let e=n({},b.value);e.action="pip_install",$.sysPythonSiteMg(e).then((e=>{t.loadingInfo.isLoading=!1,t.loadingInfo.content="",2e3==e.code?(D.success(e.msg),V(),a("refreshData")):D.warning(e.msg)}))}}))}return o({handleOpen:function(e,o){if(y.value=o,v.value=!0,e){let o=U(e);b.value.id=o.id}}}),(e,o)=>{const l=r("el-input"),a=r("el-form-item"),t=r("el-option"),n=r("el-select"),i=r("el-form"),C=r("el-button");return s(),d("div",null,[u(T,{modelValue:p(v),"onUpdate:modelValue":o[3]||(o[3]=e=>h(v)?v.value=e:v=e),title:p(y),width:"560px","before-close":V},{footer:c((()=>[u(C,{onClick:V,loading:p(j)},{default:c((()=>o[4]||(o[4]=[_("\u53d6\u6d88")]))),_:1},8,["loading"]),u(C,{type:"primary",onClick:x,loading:p(j)},{default:c((()=>o[5]||(o[5]=[_("\u4fdd\u5b58")]))),_:1},8,["loading"])])),default:c((()=>[u(i,{inline:!1,model:p(b),rules:p(w),ref_key:"rulesForm",ref:I,"label-position":"right","label-width":"auto"},{default:c((()=>[u(a,{label:"\u540d\u79f0\uff1a",prop:"name"},{default:c((()=>[u(l,{modelValue:p(b).name,"onUpdate:modelValue":o[0]||(o[0]=e=>p(b).name=e),clearable:"",placeholder:"\u8bf7\u8f93\u5165\u540d\u79f0"},null,8,["modelValue"])])),_:1}),u(a,{label:"\u7248\u672c\uff1a",prop:"version"},{default:c((()=>[u(l,{modelValue:p(b).version,"onUpdate:modelValue":o[1]||(o[1]=e=>p(b).version=e),clearable:"",placeholder:"\u53ef\u4e3a\u7a7a\uff0c\u9ed8\u8ba4\u5b89\u88c5\u6700\u65b0\u7248"},null,8,["modelValue"])])),_:1}),u(a,{label:"\u4f9d\u8d56\u6e90\uff1a",prop:"sourcename"},{default:c((()=>[u(n,{modelValue:p(b).sourcename,"onUpdate:modelValue":o[2]||(o[2]=e=>p(b).sourcename=e),placeholder:"\u8bf7\u9009\u62e9pip\u955c\u50cf\u6e90",style:{width:"100%"},filterable:""},{default:c((()=>[(s(!0),d(f,null,g(p(k),(e=>(s(),m(t,{key:e.version,label:e.version,value:e.version},null,8,["label","value"])))),128))])),_:1},8,["modelValue"])])),_:1})])),_:1},8,["model","rules"])])),_:1},8,["modelValue","title"])])}}},N={style:{display:"flex","align-items":"center",width:"100%"}},z={style:{display:"flex","align-items":"center",width:"100%"}},E={style:{display:"flex","align-items":"center",width:"100%"}},G={style:{width:"150px","padding-left":"20px"}},R={style:{background:"var(--el-fill-color-darker)",width:"100%","word-break":"break-all"}},W={class:"statusc"},A={class:"lyflex status"},J={class:"lyflex opbtn"},K={style:{"margin-bottom":"15px",display:"flex","justify-content":"space-between","align-items":"center"}},H=q({__name:"python_project",props:{data:{type:Object}},emits:["refreshStatus"],setup(e,{emit:o}){const l=S(),a=o,t=e;let g=v((()=>"windows"==l.sysConfig.currentOs));v((()=>siteThemeStore.ismobile));let q=i(!1),T=i(null),H=i(null),Q=i(!1),X=i(null),Y=i(!1),Z=i({id:null,name:"",project_log:"",error_log:"",status:!1,loadstatus:{pids:[]},conf:"",oldConf:"",info:{project_cfg:{start_method:"command",sgi:""}},old_project_cfg:{}}),ee=i(""),oe=i(!1),le=i([]),ae=i(!1),te=i(!1);let ne=i({name:[{required:!0,message:"\u8bf7\u8f93\u5165\u9879\u76ee\u540d\u79f0",trigger:"blur"}],path:[{required:!0,message:"\u8bf7\u9009\u62e9\u9879\u76ee\u6839\u76ee\u5f55",trigger:"blur"}],"project_cfg.version":[{required:!0,message:"\u8bf7\u9009\u62e9Python\u7248\u672c",trigger:"blur"}]}),ie=i([{required:!0,validator:function(e,o,l){const a=parseInt(o,10);isNaN(a)&&l(new Error("\u8bf7\u8f93\u5165\u6709\u6548\u7684\u7aef\u53e3\u53f7")),a<1||a>65534?l(new Error("\u7aef\u53e3\u53f7\u5fc5\u987b\u57280\u523065535\u4e4b\u95f4")):l()},trigger:"blur"}]),re=i([{required:!0,message:"\u8bf7\u8f93\u5165\u5e94\u7528\u53c2\u6570",trigger:"blur"}]);j((()=>Z.value.info.project_cfg.sgi),((e,o)=>{const l=Z.value.info.project_cfg;if("django"==l.framework){if(l.application&&o){let a=l.application.replace(o,e);Z.value.info.project_cfg.application=a}if(l.rukou){let o="wsgi"==e?"asgi.py":"wsgi.py",a=l.rukou.replace(o,e+".py");Z.value.info.project_cfg.rukou=a}}}));let de=v((()=>{const e=Z.value.info.project_cfg;if(!Z.value.info.path)return"";if("python"===Z.value.info.framework)return"";{let o=e.port?e.port:"\u7aef\u53e3\u672a\u914d\u7f6e",l=e.application?e.application:"\u5e94\u7528\u672a\u914d\u7f6e";if("daphne"===e.start_method)return`${e.start_method} -b ${e.host} -p ${o} ${l}`;if("uwsgi"===e.start_method)return`${e.start_method} --${e.protocol} ${e.host}:${o} --module ${l}`;if("gunicorn"===e.start_method)return"wsgi"==e.sgi?`${e.start_method} --bind ${e.host}:${o} ${l}`:"asgi"==e.sgi?`${e.start_method} --bind ${e.host}:${o} ${l} -k uvicorn.workers.UvicornWorker`:`${e.start_method} --bind ${e.host}:${o} ${l}`}}));function se(e){"daphne"==e&&(Z.value.info.project_cfg.sgi="asgi")}let ue=i("info");function ce(){Q.value=!0,L((()=>{H.value.handleOpen({path:Z.value.path,isDir:!1},"\u4f9d\u8d56\u6587\u4ef6\u9009\u62e9")}))}function pe(){Y.value=!0,L((()=>{X.value.handleOpen({path:Z.value.path,isDir:!1},"\u5165\u53e3\u6587\u4ef6\u9009\u62e9")}))}function fe(e){let o=U(e);Z.value.info.project_cfg.requirements=o}function ge(e){let o=U(e);Z.value.info.project_cfg.rukou=o,l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u9884\u83b7\u53d6\u73af\u5883\u4e2d...",$.sysGetPythonMg({action:"get_env_info",path:Z.value.path,rukou:Z.value.project_cfg.rukou}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3===e.code&&(Z.value.info.project_cfg.framework=e.data.framework,Z.value.info.project_cfg.rukou=e.data.rukou,Z.value.info.project_cfg.requirements=e.data.requirements,Z.value.info.project_cfg.sgi=e.data.sgi,Z.value.info.project_cfg.application=e.data.application,e.data.requirements&&(Z.value.info.project_cfg.install_reqs=!0))}))}function me(e="stop"){let o="\u786e\u5b9a\u542f\u52a8\u5417\uff1f",t="\u542f\u52a8\u4e2d...",n=!0;"stop"==e?(o="\u786e\u5b9a\u8981\u505c\u6b62\u5417\uff1f",t="\u505c\u6b62\u4e2d...",n=!1):"restart"==e&&(o="\u786e\u5b9a\u8981\u91cd\u542f\u5417\uff1f",t="\u91cd\u542f\u4e2d...",n=!0),B.confirm(`${o}`,"\u8b66\u544a",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((o=>{l.loadingInfo.isLoading=!0,l.loadingInfo.content=t,$.sysPythonSiteMg({id:Z.value.id,op:e,action:"set_status"}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3==e.code?(D.success(e.msg),Z.value.status=n,a("refreshStatus",{id:Z.value.id,status:n})):D.warning(e.msg)}))})).catch((()=>{}))}function _e(){let e={id:Z.value.id};l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u83b7\u53d6\u4e2d...",$.sysGetPythonSiteMg(e).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3===e.code?(Z.value.info=e.data.data[0],Z.value.old_project_cfg=U(e.data.data[0].project_cfg),"uwsgi"==Z.value.info.project_cfg.start_method||"gunicorn"==Z.value.info.project_cfg.start_method?ae.value=!0:ae.value=!1,"gunicorn"==Z.value.info.project_cfg.start_method?te.value=!0:te.value=!1):D.warning(e.msg)}))}let he=i(null);let ve=i(null);function je(e){"error_log"==e.props.name?(l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u6b63\u5728\u83b7\u53d6...",$.sysPythonSiteMg({id:Z.value.id,action:"get_project_log",log_type:"error"}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3==e.code?(Z.value.error_log=e.data,L((()=>{ve.value&&ve.value.scrollToBottom()}))):D.warning(e.msg)}))):"project_log"==e.props.name?(l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u6b63\u5728\u83b7\u53d6...",$.sysPythonSiteMg({id:Z.value.id,action:"get_project_log",log_type:"access"}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3==e.code?(Z.value.project_log=e.data,L((()=>{he.value&&he.value.scrollToBottom()}))):D.warning(e.msg)}))):"info"==e.props.name?_e():"loadstatus"===e.props.name?(l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u6b63\u5728\u83b7\u53d6\u8d1f\u8f7d\u72b6\u6001...",$.sysPythonSiteMg({id:Z.value.id,action:"get_loadstatus"}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",Z.value.loadstatus={},2e3==e.code?Z.value.loadstatus=e.data:D.warning(e.msg)}))):"edit_conf"===e.props.name?(l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u6b63\u5728\u83b7\u53d6\u914d\u7f6e\u6587\u4ef6...",$.sysPythonSiteMg({id:Z.value.id,action:"get_conf"}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3==e.code?(Z.value.conf=e.data,Z.value.oldConf=e.data):D.warning(e.msg)}))):"envmg"==e.props.name?be():"status"==e.props.name&&(l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u83b7\u53d6\u4e2d...",$.sysGetPythonSiteMg({id:Z.value.id,is_simple:!0}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3==e.code?Z.status=e.data.data[0].status:D.warning(e.msg)})))}function ye(){if(Z.value.oldConf==Z.value.conf)return void D.warning("\u914d\u7f6e\u6587\u4ef6\u672a\u53d8\u52a8\uff0c\u65e0\u9700\u4fdd\u5b58!!!");if(""==Z.value.conf||null==Z.value.conf)return void D.warning("\u914d\u7f6e\u6587\u4ef6\u9519\u8bef\uff0c\u8bf7\u68c0\u67e5\u914d\u7f6e");B.confirm("\u786e\u5b9a\u8981\u4fdd\u5b58\u914d\u7f6e\u6587\u4ef6\u5417\uff1f","\u8b66\u544a",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((e=>{l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u6b63\u5728\u4fdd\u5b58\u914d\u7f6e\u6587\u4ef6...",$.sysPythonSiteMg({id:Z.value.id,conf:Z.value.conf,action:"save_conf"}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3==e.code?D.success("\u4fdd\u5b58\u6210\u529f"):D.warning(e.msg)}))})).catch((()=>{}))}function be(e=""){le.value=[],l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u52a0\u8f7d\u4e2d...",oe.value=!0,$.sysPythonSiteMg({id:Z.value.id,action:"get_piplist",search:e}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",oe.value=!1,2e3==e.code?le.value=e.data:D.warning(e.msg)}))}function ke(){q.value=!0,L((()=>{T.value.handleOpen({id:Z.value.id},"pip\u4f9d\u8d56\u5b89\u88c5")}))}function we(){be(ee.value)}let Ve=i(null);function Ie(){Ve.value.validate((e=>{if(e){if(JSON.stringify(Z.value.old_project_cfg)==JSON.stringify(Z.value.info.project_cfg))return void D.warning("\u914d\u7f6e\u672a\u4fee\u6539\uff0c\u65e0\u9700\u4fdd\u5b58\uff01\uff01\uff01");if(Z.value.info.project_cfg.install_reqs&&P(Z.value.info.project_cfg.requirements))return void D.warning("\u60a8\u52fe\u9009\u4e86\u5b89\u88c5\u4f9d\u8d56\uff0c\u4f46\u4f9d\u8d56\u6587\u4ef6\u5374\u4e3a\u7a7a\uff01\uff01\uff01");let e=n({},Z.value.info);e.action="edit_site";let o="\u786e\u8ba4\u4fdd\u5b58\u5417\uff1f";Z.value.old_project_cfg.start_method!=Z.value.info.project_cfg.start_method?o="\u5207\u6362\u3010\u542f\u52a8\u65b9\u5f0f\u3011\u4e3a\u8017\u65f6\u64cd\u4f5c\uff0c\u786e\u8ba4\u4fdd\u5b58\u5417\uff1f":!Z.value.old_project_cfg.install_reqs&&Z.value.info.project_cfg.install_reqs&&(o="\u5b89\u88c5\u4f9d\u8d56\u4e3a\u8017\u65f6\u64cd\u4f5c\uff0c\u786e\u8ba4\u4fdd\u5b58\u5417\uff1f"),B.confirm(`${o}`,"\u8b66\u544a",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((o=>{l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u4fdd\u5b58\u4e2d...",$.sysPythonSiteMg(e).then((e=>{l.loadingInfo.isLoading=!0,l.loadingInfo.content="",2e3==e.code?(D.success(e.msg),_e()):D.warning(e.msg)}))})).catch((()=>{}))}}))}return y((()=>{Z.value.id=t.data.id,Z.value.name=t.data.name,Z.value.status=t.data.status,"info"==ue.value&&_e()})),(e,o)=>{const a=r("el-input"),t=r("el-form-item"),n=r("el-col"),i=r("el-row"),v=r("el-radio-button"),j=r("el-radio-group"),y=r("QuestionFilled"),L=r("el-icon"),S=r("el-tooltip"),U=r("el-button"),P=r("el-option"),_e=r("el-select"),xe=r("el-checkbox"),Ce=r("el-switch"),Le=r("el-form"),Se=r("el-tab-pane"),Ue=r("CaretRight"),$e=r("el-descriptions-item"),qe=r("el-descriptions"),Pe=r("el-table-column"),Oe=r("el-table"),Me=r("el-tabs"),Te=b("loading");return s(),d(f,null,[u(Me,{"tab-position":"left",modelValue:p(ue),"onUpdate:modelValue":o[23]||(o[23]=e=>h(ue)?ue.value=e:ue=e),onTabClick:je},{default:c((()=>[u(Se,{label:"\u9879\u76ee\u4fe1\u606f",name:"info"},{default:c((()=>[u(Le,{inline:!1,model:p(Z).info,rules:p(ne),ref_key:"rulesForm",ref:Ve,"label-position":"right","label-width":"auto"},{default:c((()=>[u(i,{gutter:20},{default:c((()=>[u(n,{span:12},{default:c((()=>[u(t,{label:"\u9879\u76ee\u540d\u79f0\uff1a",prop:"name"},{default:c((()=>[w("div",N,[u(a,{modelValue:p(Z).info.name,"onUpdate:modelValue":o[0]||(o[0]=e=>p(Z).info.name=e),placeholder:"\u8bf7\u8f93\u5165\u9879\u76ee\u540d\u79f0",maxlength:"50",disabled:!0},null,8,["modelValue"])])])),_:1})])),_:1}),u(n,{span:12},{default:c((()=>[u(t,{label:"Python\u7248\u672c\uff1a",prop:"project_cfg.version"},{default:c((()=>[u(a,{modelValue:p(Z).info.project_cfg.version,"onUpdate:modelValue":o[1]||(o[1]=e=>p(Z).info.project_cfg.version=e),placeholder:"\u8bf7\u8f93\u5165python\u7248\u672c",maxlength:"50",disabled:!0},null,8,["modelValue"])])),_:1})])),_:1})])),_:1}),u(t,{label:"\u542f\u52a8\u65b9\u5f0f\uff1a",prop:"project_cfg.start_method"},{default:c((()=>[u(j,{modelValue:p(Z).info.project_cfg.start_method,"onUpdate:modelValue":o[2]||(o[2]=e=>p(Z).info.project_cfg.start_method=e),onChange:se},{default:c((()=>[u(v,{label:"\u547d\u4ee4\u884c",value:"command"}),p(g)?k("",!0):(s(),m(v,{key:0,label:"uwsgi",value:"uwsgi"})),p(g)?k("",!0):(s(),m(v,{key:1,label:"gunicorn",value:"gunicorn"})),u(v,{label:"daphne",value:"daphne"})])),_:1},8,["modelValue"]),u(S,{effect:"dark",content:"\u547d\u4ee4\u884c\uff1a\u9002\u7528\u4e8epython<br/>uwsgi\uff1a\u9002\u7528\u4e8eflask\u3001django<br/>gunicorn\uff1a\u9002\u7528\u4e8eflask\u3001django<br/>daphne\uff1a\u9002\u7528\u4e8edjango","raw-content":!0,placement:"top-start"},{default:c((()=>[u(L,{style:{"margin-left":"5px"}},{default:c((()=>[u(y)])),_:1})])),_:1})])),_:1}),"command"==p(Z).info.project_cfg.start_method?(s(),m(t,{key:0,label:"\u542f\u52a8\u547d\u4ee4\uff1a",prop:"project_cfg.start_command"},{default:c((()=>[u(a,{modelValue:p(Z).info.project_cfg.start_command,"onUpdate:modelValue":o[3]||(o[3]=e=>p(Z).info.project_cfg.start_command=e),placeholder:"\u5982\uff1apip install -r requirements.txt && python manage.py runserver 0.0.0.0:8000",maxlength:"300"},null,8,["modelValue"])])),_:1})):k("",!0),u(i,{gutter:20},{default:c((()=>[u(n,{span:16},{default:c((()=>[u(t,{label:"\u9879\u76ee\u76ee\u5f55\uff1a",prop:"path"},{default:c((()=>[u(a,{modelValue:p(Z).info.path,"onUpdate:modelValue":o[4]||(o[4]=e=>p(Z).info.path=e),placeholder:"\u8bf7\u9009\u62e9\u9879\u76ee\u6839\u76ee\u5f55",class:"selectDirs",disabled:!0},null,8,["modelValue"])])),_:1})])),_:1}),u(n,{span:8},{default:c((()=>["command"!=p(Z).info.project_cfg.start_method?(s(),m(t,{key:0,label:"\u9879\u76ee\u7aef\u53e3\uff1a",prop:"project_cfg.port",rules:"command"!=p(Z).info.project_cfg.start_method?p(ie):[]},{default:c((()=>[w("div",z,[u(a,{ref:"PathInputElement",modelValue:p(Z).info.project_cfg.port,"onUpdate:modelValue":o[5]||(o[5]=e=>p(Z).info.project_cfg.port=e),placeholder:"\u8bf7\u8f93\u5165\u9879\u76ee\u7aef\u53e3",type:"number",min:"1",max:"65534"},null,8,["modelValue"])])])),_:1},8,["rules"])):k("",!0)])),_:1})])),_:1}),"command"!=p(Z).info.project_cfg.start_method?(s(),m(t,{key:1,label:"\u5165\u53e3\u6587\u4ef6\uff1a",prop:"project_cfg.rukou"},{default:c((()=>[u(a,{modelValue:p(Z).info.project_cfg.rukou,"onUpdate:modelValue":o[6]||(o[6]=e=>p(Z).info.project_cfg.rukou=e),clearable:"",placeholder:"\u9879\u76ee\u5165\u53e3\u6587\u4ef6\u5982\uff1awsgi.py\u3001asgi.py\u3001app.py",class:"selectDirs"},{prepend:c((()=>[u(U,{onClick:pe,icon:"Document",type:"primary"})])),_:1},8,["modelValue"])])),_:1})):k("",!0),u(i,{gutter:20},{default:c((()=>[u(n,{span:8},{default:c((()=>[u(t,{label:"\u9879\u76ee\u6846\u67b6\uff1a",prop:"project_cfg.framework"},{default:c((()=>[u(_e,{modelValue:p(Z).info.project_cfg.framework,"onUpdate:modelValue":o[7]||(o[7]=e=>p(Z).info.project_cfg.framework=e),placeholder:"\u8bf7\u9009\u62e9\u9879\u76ee\u6846\u67b6",disabled:!0,style:{width:"100%"},filterable:""},{default:c((()=>[u(P,{key:"django",label:"django",value:"django"}),u(P,{key:"flask",label:"flask",value:"flask"}),u(P,{key:"python",label:"python",value:"python"})])),_:1},8,["modelValue"])])),_:1})])),_:1}),u(n,{span:16},{default:c((()=>[u(t,{label:"\u5e94\u7528\u53c2\u6570\uff1a",prop:"project_cfg.application",rules:"command"!=p(Z).info.project_cfg.start_method?p(re):[]},{default:c((()=>[u(a,{modelValue:p(Z).info.project_cfg.application,"onUpdate:modelValue":o[8]||(o[8]=e=>p(Z).info.project_cfg.application=e),placeholder:"\u5982\uff1aapplication.asgi:application\u6216app:app",maxlength:"100"},null,8,["modelValue"])])),_:1},8,["rules"])])),_:1})])),_:1}),u(t,{label:"\u4f9d\u8d56\u6587\u4ef6\uff1a",prop:"project_cfg.requirements"},{default:c((()=>[w("div",E,[u(a,{modelValue:p(Z).info.project_cfg.requirements,"onUpdate:modelValue":o[9]||(o[9]=e=>p(Z).info.project_cfg.requirements=e),clearable:"",placeholder:"\u8bf7\u9009\u62e9\u4f9d\u8d56\u6587\u4ef6\uff0c\u5982\uff1arequirements.txt",class:"selectDirs"},{prepend:c((()=>[u(U,{onClick:ce,icon:"Document",type:"primary"})])),_:1},8,["modelValue"]),w("div",G,[u(xe,{modelValue:p(Z).info.project_cfg.install_reqs,"onUpdate:modelValue":o[10]||(o[10]=e=>p(Z).info.project_cfg.install_reqs=e),label:"\u5b89\u88c5\u4f9d\u8d56"},null,8,["modelValue"])])])])),_:1}),u(i,{gutter:20},{default:c((()=>["command"!=p(Z).info.project_cfg.start_method?(s(),m(n,{key:0,span:12},{default:c((()=>["command"!=p(Z).info.project_cfg.start_method?(s(),m(t,{key:0,label:"\u901a\u8baf\u534f\u8bae\uff1a",prop:"project_cfg.sgi"},{default:c((()=>[u(_e,{modelValue:p(Z).info.project_cfg.sgi,"onUpdate:modelValue":o[11]||(o[11]=e=>p(Z).info.project_cfg.sgi=e),placeholder:"\u8bf7\u9009\u62e9\u901a\u8baf\u534f\u8bae",disabled:"daphne"==p(Z).info.project_cfg.start_method,style:{width:"100%"},filterable:""},{default:c((()=>[u(P,{key:"wsgi",label:"wsgi",value:"wsgi",disabled:"daphne"==p(Z).info.project_cfg.start_method},null,8,["disabled"]),u(P,{key:"asgi",label:"asgi",value:"asgi"})])),_:1},8,["modelValue","disabled"])])),_:1})):k("",!0)])),_:1})):k("",!0),u(n,{span:12},{default:c((()=>[p(g)?k("",!0):(s(),m(t,{key:0,label:"\u542f\u52a8\u7528\u6237\uff1a",prop:"project_cfg.start_user"},{default:c((()=>[u(_e,{modelValue:p(Z).info.project_cfg.start_user,"onUpdate:modelValue":o[12]||(o[12]=e=>p(Z).info.project_cfg.start_user=e),placeholder:"\u8bf7\u9009\u62e9\u542f\u52a8\u7528\u6237",style:{width:"100%"},clearable:"",filterable:""},{default:c((()=>[u(P,{key:"root",label:"root",value:"root"}),u(P,{key:"www",label:"www",value:"www"})])),_:1},8,["modelValue"])])),_:1}))])),_:1})])),_:1}),u(i,null,{default:c((()=>[u(n,{span:5},{default:c((()=>[u(t,{label:"\u5f00\u673a\u542f\u52a8\uff1a"},{default:c((()=>[u(Ce,{modelValue:p(Z).info.project_cfg.autostart,"onUpdate:modelValue":o[13]||(o[13]=e=>p(Z).info.project_cfg.autostart=e),"inline-prompt":"",style:{"--el-switch-on-color":"#13ce66","--el-switch-off-color":"#ff4949"},"active-text":"\u5f00\u542f","inactive-text":"\u5173\u95ed"},null,8,["modelValue"])])),_:1})])),_:1}),"uwsgi"==p(Z).info.project_cfg.start_method?(s(),m(n,{key:0,span:6},{default:c((()=>[u(t,{label:"\u901a\u4fe1\u65b9\u5f0f\uff1a"},{default:c((()=>[u(_e,{modelValue:p(Z).info.project_cfg.protocol,"onUpdate:modelValue":o[14]||(o[14]=e=>p(Z).info.project_cfg.protocol=e),placeholder:"\u8bf7\u9009\u62e9\u901a\u4fe1\u65b9\u5f0f",filterable:""},{default:c((()=>[u(P,{key:"http",label:"http",value:"http"}),u(P,{key:"socket",label:"socket",value:"socket"})])),_:1},8,["modelValue"])])),_:1})])),_:1})):k("",!0),"command"!=p(Z).info.project_cfg.start_method?(s(),m(n,{key:1,span:7},{default:c((()=>[u(t,{label:"\u76d1\u542c\u5730\u5740\uff1a"},{default:c((()=>[u(_e,{modelValue:p(Z).info.project_cfg.host,"onUpdate:modelValue":o[15]||(o[15]=e=>p(Z).info.project_cfg.host=e),placeholder:"\u8bf7\u9009\u62e9\u76d1\u542c\u5730\u5740",filterable:""},{default:c((()=>[u(P,{key:"0.0.0.0",label:"0.0.0.0",value:"0.0.0.0"}),u(P,{key:"127.0.0.1",label:"127.0.0.1",value:"127.0.0.1"})])),_:1},8,["modelValue"])])),_:1})])),_:1})):k("",!0)])),_:1}),p(de)?(s(),m(t,{key:2,label:"\u8f85\u52a9\u9884\u89c8\uff1a"},{default:c((()=>[w("div",R,V(p(de)),1)])),_:1})):k("",!0),u(t,{label:" "},{default:c((()=>[u(U,{type:"primary",onClick:Ie},{default:c((()=>o[27]||(o[27]=[_("\u4fdd\u5b58\u5e76\u91cd\u542f")]))),_:1})])),_:1})])),_:1},8,["model","rules"])])),_:1}),u(Se,{label:"\u670d\u52a1\u72b6\u6001",name:"status"},{default:c((()=>[w("div",W,[w("div",A,[w("div",null,"\u5f53\u524d\u72b6\u6001\uff1a"+V(p(Z).status?"\u5df2\u542f\u52a8":"\u5df2\u505c\u6b62"),1),u(L,{class:I(p(Z).status?"on":"off")},{default:c((()=>[u(Ue)])),_:1},8,["class"])]),w("div",J,[u(U,{onClick:o[16]||(o[16]=e=>me("start")),disabled:p(Z).status},{default:c((()=>o[28]||(o[28]=[_("\u542f\u52a8")]))),_:1},8,["disabled"]),u(U,{onClick:o[17]||(o[17]=e=>me("stop")),disabled:!p(Z).status},{default:c((()=>o[29]||(o[29]=[_("\u505c\u6b62")]))),_:1},8,["disabled"]),u(U,{onClick:o[18]||(o[18]=e=>me("restart"))},{default:c((()=>o[30]||(o[30]=[_("\u91cd\u542f")]))),_:1})])])])),_:1}),p(ae)?(s(),m(Se,{key:0,label:"\u914d\u7f6e\u4fee\u6539",name:"edit_conf"},{default:c((()=>[u(O,{modelValue:p(Z).conf,"onUpdate:modelValue":o[19]||(o[19]=e=>p(Z).conf=e),fontSize:"13px",placeholder:p(Z).conf?"":"\u672a\u83b7\u53d6\u914d\u7f6e\u6587\u4ef6",showLineNums:!0,lineWrapping:!0,mode:"javascript",height:"60vh","read-only":!1,ref:"lyCodemirrorConf"},null,8,["modelValue","placeholder"]),u(U,{type:"primary",style:{"margin-top":"10px","margin-bottom":"10px"},onClick:ye},{default:c((()=>o[31]||(o[31]=[_("\u4fdd\u5b58\u5e76\u91cd\u542f")]))),_:1}),o[32]||(o[32]=w("div",{class:"ry-cj-care"},[w("li",null,"\u82e5\u60a8\u4e0d\u4e86\u89e3\u914d\u7f6e\u6587\u4ef6\u89c4\u5219\uff0c\u8bf7\u52ff\u968f\u610f\u4fee\u6539!!!"),w("li",null,"\u5feb\u6377\u952e CTRL+F \u67e5\u627e\u548c\u66ff\u6362\u5185\u5bb9")],-1))])),_:1})):k("",!0),u(Se,{label:"\u8d1f\u8f7d\u72b6\u6001",name:"loadstatus"},{default:c((()=>[u(qe,{border:!0,column:2,direction:"vertical",title:"\u8fd0\u884c\u8d1f\u8f7d"},{default:c((()=>[u($e,{label:"CPU\u4f7f\u7528\u7387(%)"},{default:c((()=>[_(V(p(Z).loadstatus.cpu_p||"-"),1)])),_:1}),u($e,{label:"\u5185\u5b58\u4f7f\u7528\u7387(%)"},{default:c((()=>[_(V(p(Z).loadstatus.mem_p||"-"),1)])),_:1}),u($e,{label:"\u4f7f\u7528\u5185\u5b58(USS)"},{default:c((()=>[_(V(p(Z).loadstatus.mem_used||"-"),1)])),_:1}),u($e,{label:"\u542f\u52a8\u7528\u6237"},{default:c((()=>[_(V(p(Z).loadstatus.user||"-"),1)])),_:1}),u($e,{label:"\u7ebf\u7a0b\u6570"},{default:c((()=>[_(V(p(Z).loadstatus.threads||"-"),1)])),_:1}),u($e,{label:"\u8fdb\u7a0bpid\u5217\u8868(pids)"},{default:c((()=>[_(V(p(Z).loadstatus.pids.join("\u3001")||"-"),1)])),_:1}),u($e,{label:"\u7236\u8fdb\u7a0bpid/name"},{default:c((()=>[_(V(p(Z).loadstatus.fpid?p(Z).loadstatus.fpid+"/"+p(Z).loadstatus.fpid_name:"-"),1)])),_:1}),u($e,{label:"\u521b\u5efa\u65f6\u95f4(create_time)"},{default:c((()=>[_(V(p(Z).loadstatus.create_time||"-"),1)])),_:1}),u($e,{label:"\u547d\u4ee4\u884c(cmdline)"},{default:c((()=>[_(V(p(Z).loadstatus.cmdline||"-"),1)])),_:1})])),_:1})])),_:1}),u(Se,{label:"\u73af\u5883\u7ba1\u7406",name:"envmg"},{default:c((()=>[w("div",K,[u(U,{type:"primary",onClick:ke},{default:c((()=>o[33]||(o[33]=[_("\u5b89\u88c5\u5e93")]))),_:1}),u(a,{style:{width:"320px"},modelValue:p(ee),"onUpdate:modelValue":o[20]||(o[20]=e=>h(ee)?ee.value=e:ee=e),clearable:"",onClear:we,onKeyup:C(we,["enter"]),placeholder:"\u641c\u7d22\u540d\u79f0"},{append:c((()=>[u(U,{icon:"Search",onClick:we})])),_:1},8,["modelValue"])]),x((s(),m(Oe,{data:p(le),"max-height":500,border:""},{default:c((()=>[u(Pe,{prop:"name",label:"\u540d\u79f0","min-width":"160","show-overflow-tooltip":""}),u(Pe,{prop:"version",label:"\u7248\u672c","min-width":"100"}),u(Pe,{label:"\u64cd\u4f5c",width:"100"},{default:c((e=>[u(U,{link:"",type:"primary",onClick:o=>{var a;"pip"!=(a=e.row).name?B.confirm(`\u786e\u8ba4\u8981\u5378\u8f7d\u3010${a.name}\u3011\u5417\uff1f`,"\u8b66\u544a",{closeOnClickModal:!1,cancelButtonText:"\u53d6\u6d88",confirmButtonText:"\u786e\u5b9a",type:"warning"}).then((e=>{l.loadingInfo.isLoading=!0,l.loadingInfo.content="\u5378\u8f7d\u4e2d...",$.sysPythonSiteMg({id:Z.value.id,action:"pip_uninstall",name:a.name}).then((e=>{l.loadingInfo.isLoading=!1,l.loadingInfo.content="",2e3==e.code?(D.success(e.msg),be()):D.warning(e.msg)}))})).catch((()=>{})):D.warning("\u4e0d\u5efa\u8bae\u5378\u8f7d\u6b64\u5e93\uff01\uff01\uff01")}},{default:c((()=>o[34]||(o[34]=[_("\u5378\u8f7d")]))),_:2},1032,["onClick"])])),_:1})])),_:1},8,["data"])),[[Te,p(oe)]])])),_:1}),u(Se,{label:"\u9879\u76ee\u65e5\u5fd7",name:"project_log"},{default:c((()=>[u(O,{modelValue:p(Z).project_log,"onUpdate:modelValue":o[21]||(o[21]=e=>p(Z).project_log=e),fontSize:"13px",placeholder:p(Z).project_log?"":"\u5f53\u524d\u6ca1\u6709\u65e5\u5fd7\uff01",showLineNums:!0,lineWrapping:!0,mode:"log",height:"68vh","read-only":!0,ref_key:"lyCodemirrorAccessLog",ref:he},null,8,["modelValue","placeholder"])])),_:1}),p(te)?(s(),m(Se,{key:1,label:"\u9519\u8bef\u65e5\u5fd7",name:"error_log"},{default:c((()=>[u(O,{modelValue:p(Z).error_log,"onUpdate:modelValue":o[22]||(o[22]=e=>p(Z).error_log=e),fontSize:"13px",placeholder:p(Z).error_log?"":"\u5f53\u524d\u6ca1\u6709\u65e5\u5fd7\uff01",showLineNums:!0,lineWrapping:!0,mode:"log",height:"68vh","read-only":!0,ref_key:"lyCodemirrorErrorLog",ref:ve},null,8,["modelValue","placeholder"])])),_:1})):k("",!0)])),_:1},8,["modelValue"]),p(Q)?(s(),m(M,{key:0,ref_key:"chooseFileShowFlag",ref:H,onChange:fe,onClosed:o[24]||(o[24]=e=>h(Q)?Q.value=!1:Q=!1),onlyFileSelect:!0},null,512)):k("",!0),p(Y)?(s(),m(M,{key:1,ref_key:"chooseRKFileShowFlag",ref:X,onChange:ge,onClosed:o[25]||(o[25]=e=>h(Y)?Y.value=!1:Y=!1),onlyFileSelect:!0},null,512)):k("",!0),p(q)?(s(),m(F,{key:2,ref_key:"installpipShowFlag",ref:T,onClosed:o[26]||(o[26]=e=>h(q)?q.value=!1:q=!1),onRefreshData:be},null,512)):k("",!0)],64)}}},[["__scopeId","data-v-bc164ab5"]]);export{H as default};
