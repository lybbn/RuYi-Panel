import"./element-plus.CMBwCou9.js";import{_ as e}from"./_plugin-vue_export-helper.BCo6x5W8.js";import{b as l,j as o,e as a,ag as t,aq as s,o as n,c as d,P as u,a6 as c,H as i,B as r,a as p,C as f,M as g,u as y,G as v,K as _,I as b,t as h}from"./@vue.BluSRtaz.js";const m={class:"ly-dialog"},C=["id"],k={class:"ly-dialog__headerbtn"},B=["onClick"],w={style:{height:"100%"}},S=e({__name:"dialog",props:{title:{type:String,default:""},modelValue:{type:Boolean,default:!0},width:{type:String,default:"50%"},center:{type:Boolean,default:!1},top:{type:String,default:"10vh"},draggable:{type:Boolean,default:!0},appendToBody:{type:Boolean,default:!1},closeOnClickModal:{type:Boolean,default:!1},fullscreen:{type:Boolean,default:!1},showFullScreen:{type:Boolean,default:!0},showClose:{type:Boolean,default:!0},loading:{type:Boolean,default:!1},beforeClose:Function},emits:["closed","onChangeFullScreen"],setup(e,{expose:S,emit:F}){const V=F;let j=l(null),M=l(!1),$=l(!1);const x=e;function I(){V("closed")}function O(){$.value=!$.value,V("onChangeFullScreen",$.value)}return o((()=>{$.value=x.fullscreen,M.value=x.modelValue,V("onChangeFullScreen",$.value)})),a((()=>x.modelValue),(e=>{M.value=e}),{deep:!0}),a((()=>x.fullscreen),(e=>{$.value=e}),{deep:!0}),S({getRef:function(){return j.value}}),(l,o)=>{const a=t("Minus"),S=t("el-icon"),F=t("full-screen"),V=t("close"),x=t("el-dialog"),R=s("loading");return n(),d("div",m,[u(x,{modelValue:y(M),"onUpdate:modelValue":o[0]||(o[0]=e=>h(M)?M.value=e:M=e),"close-on-click-modal":e.closeOnClickModal,title:e.title,width:e.width,top:e.top,fullscreen:y($),center:e.center,"before-close":e.beforeClose,"append-to-body":e.appendToBody,"destroy-on-close":!0,draggable:e.draggable,"show-close":!1,onClosed:I,ref_key:"lyDialogRef",ref:j},c({header:i((({close:o,titleId:t,titleClass:s})=>[p("div",null,[r(l.$slots,"header",{},(()=>[p("span",{id:t,class:f(s)},g(e.title),11,C)]),!0),p("div",k,[e.showFullScreen?(n(),d("button",{key:0,"aria-label":"fullscreen",type:"button",onClick:O},[y($)?(n(),v(S,{key:0,class:"el-dialog__close"},{default:i((()=>[u(a)])),_:1})):(n(),v(S,{key:1,class:"el-dialog__close"},{default:i((()=>[u(F)])),_:1}))])):_("",!0),e.showClose?(n(),d("button",{key:1,"aria-label":"close",type:"button",onClick:o},[u(S,{class:"el-dialog__close"},{default:i((()=>[u(V)])),_:1})],8,B)):_("",!0)])])])),default:i((()=>[b((n(),d("div",w,[r(l.$slots,"default",{},void 0,!0)])),[[R,e.loading]])])),_:2},[l.$slots.footer?{name:"footer",fn:i((()=>[r(l.$slots,"footer",{},void 0,!0)])),key:"0"}:void 0]),1032,["modelValue","close-on-click-modal","title","width","top","fullscreen","center","before-close","append-to-body","draggable"])])}}},[["__scopeId","data-v-4594f1b0"]]);export{S as L};
