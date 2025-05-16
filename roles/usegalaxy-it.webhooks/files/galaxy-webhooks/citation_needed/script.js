$(document).ready(function() {

    var citationNeededView = Backbone.View.extend({
        el: '#citation_needed',

        appTemplate: _.template(
            '<div id="cit_need-header">' +
                '<h3>We need your support ...</h3>' +
            '</div>' +
            '<div id="cit_need-body">' +
            'If Galaxy helped with the analysis of your data, please do not forget to <b>cite</b>:' +
            '<div id="cit_need-citation">'+
            'The Galaxy platform for accessible, reproducible, and collaborative data analyses: 2024 update<br>'+
            'Nucleic Acids Research, gkae410<br>'+
            'doi:10.1093/nar/gkae410'+
            '</div>' +
            'And please <b>acknowledge</b> the European Italian server:' +
            '<div id="cit_need-citation">'+
            'The UseGalaxy.it server is provided with the support of ELIXIR-ITALY, ReCaS-Bari, Consortium GARR, CINECA and University of Milan. UseGalaxy.it is funded by ELIXIR-IIB internal funding, the European Commission Horizon Europe research and innovation program under grant agreements with ID 101057388 (EuroScienceGateway), the National Recovery and Resilience Plan (PNRR) project ELIXIRNextGenIT [R0000010], and the PON project CNR.Biomics [PIR01_00017].' +            '</div>' +
            '</div>'
        ),


        initialize: function() {
            var me = this;
            this.render();
        },

        render: function() {
            this.$el.html(this.appTemplate());
            return this;
        }

    });

    var citNeedApp = new citationNeededView;

});
