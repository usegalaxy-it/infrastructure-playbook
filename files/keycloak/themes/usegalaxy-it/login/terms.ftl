<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        ${msg("termsTitle")}
    <#elseif section = "form">
        <div id="kc-terms-text" class="usegalaxy-it-terms" tabindex="0">
            <section id="kc-aup">
                <h2>${msg("aupHeading")}</h2>
                ${kcSanitize(msg("aupText"))?no_esc}
            </section>
            <section id="kc-tou">
                <h2>${msg("touHeading")}</h2>
                ${kcSanitize(msg("termsText"))?no_esc}
            </section>
            <section id="kc-privacy">
                <h2>${msg("privacyHeading")}</h2>
                ${kcSanitize(msg("privacyText"))?no_esc}
            </section>
        </div>
        <p class="usegalaxy-it-terms-note">${msg("termsAcceptNote")}</p>
        <form class="form-actions" action="${url.loginAction}" method="POST">
            <input class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonLargeClass!}" name="accept" id="kc-accept" type="submit" value="${msg("doAccept")}"/>
            <input class="${properties.kcButtonClass!} ${properties.kcButtonDefaultClass!} ${properties.kcButtonLargeClass!}" name="cancel" id="kc-decline" type="submit" value="${msg("doDecline")}"/>
        </form>
        <div class="clearfix"></div>
    </#if>
</@layout.registrationLayout>
