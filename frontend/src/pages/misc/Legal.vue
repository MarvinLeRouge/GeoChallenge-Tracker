<!-- src/pages/MentionsLegales.vue -->
<template>
    <div class="max-w-3xl mx-auto p-6 space-y-6">
        <h1 class="text-2xl font-semibold">Mentions légales</h1>

        <p class="text-sm text-gray-600">Dernière mise à jour : 3 octobre 2025</p>

        <section class="bg-white p-4 rounded-lg shadow-sm">
            <h2 class="text-lg font-medium mb-2">Éditeur</h2>
            <p>
                Ce site est édité et exploité à titre personnel par <strong>Jean Ceugniet</strong>,
                de nationalité française.
            </p>
            <p class="mt-2">
                Usage actuel : expérimental, non commercial. Les comptes sont validés manuellement
                par l'éditeur avant activation.
            </p>
        </section>

        <section class="bg-white p-4 rounded-lg shadow-sm">
            <h2 class="text-lg font-medium mb-2">Hébergement</h2>
            <p>
                Le site est hébergé sur un serveur privé virtuel (VPS) fourni par <strong>DigitalOcean</strong>.
            </p>
        </section>

        <section class="bg-white p-4 rounded-lg shadow-sm">
            <h2 class="text-lg font-medium mb-2">Base de données & données personnelles</h2>
            <p>
                Les données applicatives (comptes, userChallenges, logs liés à l'usage) sont stockées
                dans une base <strong>MongoDB</strong>. Les données collectées sont limitées à l'usage
                nécessaire au fonctionnement du service expérimental.
            </p>
            <p class="mt-2 text-sm text-gray-600">
                Conformément au Règlement général sur la protection des données (RGPD), vous disposez
                d'un droit d'accès, de rectification, de suppression et de portabilité de vos données.
                Pour exercer ces droits, contactez l'éditeur à l'adresse prévue ci-dessous.
            </p>
        </section>

        <section class="bg-white p-4 rounded-lg shadow-sm">
            <h2 class="text-lg font-medium mb-2">Utilisation des cookies</h2>
            <p>
                Le site peut utiliser des cookies techniques pour la navigation et la session.
                Aucun cookie analytique commercialisé n'est présent dans la configuration par défaut.
            </p>
        </section>

        <section class="bg-white p-4 rounded-lg shadow-sm">
            <h2 class="text-lg font-medium mb-2">Responsabilité</h2>
            <p>
                Les informations publiées sur ce site sont fournies à titre indicatif. L'éditeur met
                en œuvre ses meilleurs efforts pour assurer l'exactitude des contenus, mais ne saurait
                garantir l'exhaustivité ou l'absence d'erreurs. L'éditeur n'est pas responsable des
                dommages directs ou indirects résultant de l'utilisation du site.
            </p>
        </section>

        <section class="bg-white p-4 rounded-lg shadow-sm">
            <h2 class="text-lg font-medium mb-2">Propriété intellectuelle</h2>
            <p>
                Tous les éléments présents sur ce site (textes, logos, images, code) sont la propriété
                de l'éditeur ou de leurs auteurs respectifs. Toute reproduction totale ou partielle
                est interdite sans autorisation préalable.
            </p>
        </section>

        <section class="bg-white p-4 rounded-lg shadow-sm">
            <h2 class="text-lg font-medium mb-2">Contact</h2>
            <p>
                Pour toute question relative aux mentions légales, aux données personnelles ou à la
                modération des comptes, contactez :
            </p>
            <p class="mt-2 font-medium">Jean Ceugniet</p>
            <p class="text-sm text-gray-700">Localisation : France</p>
            <p class="mt-2">Email : <a class="text-blue-600"
                    href="mailto:jean.ceugniet@gmail.com">jean.ceugniet@gmail.com</a></p>
        </section>

        <section class="bg-white p-4 rounded-lg shadow-sm">
            <h2 class="text-lg font-medium mb-2">Protection des données (RGPD)</h2>
            <p>
                En application du Règlement général sur la protection des données (UE) 2016/679,
                vous pouvez exercer vos droits d'accès, de rectification, d'effacement, de limitation,
                d'opposition et de portabilité de vos données personnelles en écrivant à
                <a href="mailto:jean.ceugniet@gmail.com" class="text-blue-600">jean.ceugniet@gmail.com</a>.
            </p>
            <p class="mt-2">
                Vos données sont utilisées uniquement dans le cadre expérimental du service,
                ne font l'objet d'aucune exploitation commerciale, et ne sont ni cédées ni revendues à des tiers.
            </p>
        </section>
        <p class="text-xs text-gray-500">
            Note : ce service est fourni à titre expérimental et non commercial. Les comptes sont
            validés manuellement par l'éditeur ; toute utilisation abusive est susceptible d'entraîner
            la suspension du compte.
        </p>
    </div>
</template>

<script setup lang="ts">
// Composant statique : aucun script requis pour la version de test.
</script>

<style scoped>
/* light tweaks si besoin */
</style>