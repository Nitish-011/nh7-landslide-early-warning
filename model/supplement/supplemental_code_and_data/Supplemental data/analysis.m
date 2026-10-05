%% Landslides along the Rishikesh–Joshimath National Highway (NH-58)

%% Requirements
% The script requires MATLAB (2022b) including following toolboxes
% - Image Processing Toolbox
% - Mapping Toolbox
% - Optimization Toolbox
% - Statistics and Machine Learning Toolbox
% - Parallel Computing Toolbox (recommended)
% - Bayesreg https://de.mathworks.com/matlabcentral/fileexchange/60823-flexible-bayesian-penalized-regression-modelling
% - TopoToolbox https://github.com/wschwanghart/topotoolbox


%% Load data

% DEM
% warning off
DEM = GRIDobj('DEM\DEM.tif');
% warning on
% DEM = reproject2utm(DEM,10);

% Road
MS   = shaperead('roads\road_utm_dissolved.shp');
MSRW = shaperead('roads\road_widening.shp');

% Mapped landslide locations
LS     = shaperead('landslides\landslide_mapping\landslides_utm44n.shp');
lstype = [LS.class]';
id = lstype ~= 0 & lstype ~= 5 & lstype ~= 2;
LS(~id) = [];
lstype = [LS.react]';

% lstype (period of occurrence DD-MM-YY)
% 0 - in shadow
% 1 - 05-05-22 -- 18-10-22
% 2 - 11-04-21 -- 14-03-22
% 3 - 14-03-22 -- 05-05-22
% 4 - 14-03-22 -- 18-10-22
% 5 - before 2022
% 6 - 17-11-21 -- 18-10-22
% 7 - 31-05-22 -- 18-10-22
% 8 - 27-10-21 -- 18-10-22
% 9 - 25-12-21 -- 18-10-22
%10 - 13-08-22 -- 18-10-22
%11 - 31-12-21 -- 18-10-22
%12 - 08-02-22 -- 18-10-22

lstypedescribe = {'New LS', 'Reactivated LS'}';

%% Draw pie chart

c = histcounts(lstype,'BinMethod','integers','Normalization','probability');

colormap(brighten(parula,0.5))
cstr = string(num2str(c'*100,'%6.1f'));
cstr = string(lstypedescribe) + " (" + cstr + "%)";

figure
pie(c,cstr)

%% Derive road as a "stream network" and PPS-TopoToolbox object

% The trick to store the road network as a stream network, is to derive a
% pseudo-topographic surface which ensures that a stream profile derived
% from this surface runs along the road. 

DEM2 = DEM;
ROAD = line2GRIDobj(DEM,MS);
ix  = find(ROAD.Z,1,'first');
D   = bwdistgeodesic(ROAD.Z,ix);
DEM2.Z = D;
FD  = FLOWobj(DEM2);
S   = STREAMobj(FD,'minarea',0);
S   = trunk(S);
D   = dilate(DEM,ones(5));

xy  = [[LS.X]' [LS.Y]'];
P   = PPS(S,'pp',xy,'z',DEM);
clear DEM2

%% Road widening
RW  = polygon2GRIDobj(DEM,MSRW);


%% Rainfall data

% The following code loads the rain data compiled by Ravi and interpolates
% it to the same grid geometry as the DEM

useyear = true;
if ~useyear
    fn = "rainfall\Ramganga Confluence Rainfall Oct.xlsx";
    sn = sheetnames(fn);
    STR = struct;
    for r = 1:numel(sn)
        R = readtable(fn,"Sheet",sn(r),"ReadVariableNames",true);
        [x,y] = projfwd(DEM.georef.mstruct,R.lat,R.lon);
        accumrain = sum(table2array(R(:,3:end)),2);

        STR.(sn{r}) = interp2GRIDobj(DEM,x,y,accumrain);
    end

else
    % Data acquisition was on Oct 10, 2022. Hence, rainfalls
    % of the year are only accumulated until then.
    doy = day(datetime(2022,10,10),'dayofyear');

    % Load daily rainfall for 2022
    rain = load('rainfall\Ramganga_2022_daily.mat');
    rain = cell2struct( struct2cell(rain), {'CHIRPSv2', 'IMD1', 'IMD2', 'IMERG','MSWEP'});
    sn   = fieldnames(rain);
    
    STR = struct;
    for r = 1:numel(sn)
        switch sn{r}
            case {'IMD1','IMD2'}
                [x,y] = projfwd(DEM.georef.mstruct,rain.(sn{r})(:,1),rain.(sn{r})(:,2));
            otherwise
                [x,y] = projfwd(DEM.georef.mstruct,rain.(sn{r})(:,2),rain.(sn{r})(:,1));
        end
        accumrain = sum(rain.(sn{r})(:,3:doy+2),2);

        STR.(sn{r}) = interp2GRIDobj(DEM,double(x),double(y),double(accumrain));
    end
end


%% Visualize rainfall

% Find maximum in all rainfall products to apply a consistent colorbar to
% all axes.
mx = 0;
for r = 1:numel(sn)
    mx = max(max(STR.(sn{r})),mx);
end
    
figure
tiledlayout(2,3,'TileSpacing','none');
fn = fieldnames(STR);
for r = 1:numel(fn)
    nexttile
    imageschs(DEM,STR.(fn{r}),'usepermanent',true,'ticklabels','nice',...
        'colormap',flowcolor(255),'caxis',[0 mx],'colorbar',false);
    padextent([0 -20000 0 0],gca)
    niceticks
    hold on
    plot(P.S,'color','k','LineWidth',2)
    spl(r) = subplotlabel(gca,fn{r},'Location','northwestoutside');

    if ismember(r,[2 3 5])
        yticks([])
    end

    if r == numel(fn)
        colormap(flowcolor(255))
        h = colorbar(gca);
        h.Label.String = 'Acc. rainfall [mm]';
        clim([0 mx])
    end
end
set(gcf,'Position',[277.8000  257.0000  770.2000  505.0000])
exportgraphics(gcf,'images/Fig_03_rainfall.png','Resolution',300)

%% Create covariates (gradient next to road)

% Calculate the area upslope to the road in a certain buffer width
buffwidth = 7; % px
DEMR      = GRIDobj(DEM)+inf;
DEMR.Z(S.IXgrid) = getnal(S,DEM);
DMIN      = erode(DEMR,ones(buffwidth));
I         = DMIN < DEM;
I.Z(S.IXgrid) = true;
stats     = regionprops(I.Z);
I.Z       = bwareaopen(I.Z,stats(1).Area-5,8);

[~,L] = bwdist(~isnan(ROAD.Z),'euclidean');
G     = GRIDobj("DEM\gdalslope.tif");
gm    = accumarray(L(I.Z),G.Z(I.Z),[prod(G.size) 1],@mean,single(nan));
GM    = GRIDobj(DEM);
GM.Z  = reshape(gm,GM.size);
gm    = inpaintnans(S,GM);

%% What is the optimal smoothing
% First explore the sensitivity of the deviance
maxslope = 40; % degrees
k = logspace(-1,4,50);
dev = cellfun(@(k) fitloglinear(P,min(smooth(S,gm,'k',k),maxslope)).Deviance,num2cell(k));

figure
semilogx(k,dev,'O-')
xlabel('K')
ylabel('Deviance')

% Optimize model deviance by minimizing deviance
k = fminsearch(@(k) fitloglinear(P,min(smooth(S,gm,'k',exp(k)),maxslope)).Deviance, 0);
k = exp(k);
xline(k,'--',['Optimal K = ' num2str(k,2)])
gms = smooth(S,gm,'k',k);

gms = min(gms,maxslope);


%% Create covariates (geology)

GEOG = GRIDobj('geology\Lithology_simplified_raster.tif');
GEOG.Z(GEOG.Z == 4 | GEOG.Z == 0) = nan;
I = ~isnan(GEOG);
[~,L] = bwdist(I.Z,'euclidean');
GEOG.Z = GEOG.Z(L);
GEOG = filter(GEOG,'median',[5 5]);
geog = interp(GEOG,P.S.x,P.S.y,'nearest');
geog = round(geog);
[~,~,geog] = unique(geog);



%% Which rainfall product to use?

% P2 = P;
% P2.PP = P2.PP(lstype ~= 2 & lstype ~= 5 & lstype ~= 0 ); 
% P = P2;
c = fieldnames(STR);

AICr = zeros(numel(c),1);

for  r = 1:numel(c)
    mdlrain = fitloglinear(P,{STR.(c{r}) gms geog RW},'CategoricalVars',[3 4],'Intercept',true);
    figure('Position',1e3*[0.2418    0.1802    1.1880    0.5818])
    ploteffects(P,mdlrain,[1 2 3 4],'indicators',true,'patch',true,...
        'plotintensity',true,'varnames', {['Rainfall ' c{r}]  'Slope' 'Lithozone' 'Road widening'});
    drawnow

    ax = findall(gcf,'Type','Axes');
    ax(4).XLabel.String = 'Acc. rainfall [mm]';
    ax(4).YLabel.String = '\lambda [m^{-1}]';
    
    ax(3).XLabel.String = 'Gradient [°]';
    ax(3).YLabel.String = '\lambda [m^{-1}]';

    ax(2).XLabel.String = 'Lithozones [°]';
    ax(2).YLabel.String = '\lambda [m^{-1}]';

    ax(1).YLabel.String = '\lambda [m^{-1}]';
    
    spl = subplotlabel(gcf,'a','location','nw','pre','(','post',')','fontsize',12);

    exportgraphics(gcf,['images/ploteffects' c{r} '.png'],'resolution',300);
    close
    AICr(r) = mdlrain.ModelCriterion.AIC;
end

%% Landslide susceptibility model

% Bayesian
[mdl,int,intci,predstats,ranks] = bayesloglinear(P,...
                                {STR.CHIRPSv2 gms geog RW},...
                                'catvars',[3 4],'prior','lasso',...
                                'waic',false);

%% Plot posterior samples
beta = [mdl.beta; mdl.beta0];
figure('Position',1e3*[0.2466    0.0818    1.0912    0.6802])
[hS,AX,BigAx,H,HAx] = plotmatrix(beta');

% delete upper part of the plotmatrix
I = triu(ones(size(beta,1)))>0;
for r = 1:numel(I)
    if I(r); delete(AX(r)); end
end
VARS = {'CHIRPS v2', 'Gradient', 'Lithozone 2', 'Lithozone 3',...
        'Lithozone 4' 'Lithozone 5' 'Road widened' 'Intercept'};

% Some help about the output of plotmatrix
% S – Chart line objects for the scatter plots
% AX – Axes objects for each subaxes
% BigAx – Axes object for big axes that frames the subaxes
% H – Histogram objects for the histogram plots
% HAx – Axes objects for the invisible histogram axes

for r = 1:numel(HAx)
    m = mean(beta(r,:));
    hdiLim = mbe_hdi(beta(r,:),0.95);
    H(r).EdgeColor = 'none';
    H(r).FaceColor = [0.5059 0.8471 0.8157];
    xline(HAx(r),m,'-',num2str(m,2),'LineWidth',2,'Color','k','FontSize',8);
    xline(HAx(r),hdiLim,':',{num2str(hdiLim(1),2), num2str(hdiLim(2),2)},...
        'LineStyle',':','LineWidth',2,'FontSize',8)
    xline(HAx(r),0,'LineWidth',1,'Color',[.5 .5 .5],'LineStyle','--')
    spl(r) = subplotlabel(HAx(r),VARS{r},'location','northwestoutside',...
        'FontSize',12);
    if r == numel(HAx)
        HAx(r).XTick = AX(end,1).YTick;
    end
end

exportgraphics(gcf,'images/Fig_04_posteriors.png','Resolution',300)

%% Plot results
figure
xmax = max(S.distance)/1000; %[km]
nplots = 7;
subplot(nplots,1,1)
plotdz(P,'dunit','km','z',smooth(S,DEM,'k',1000),'Size',2)
xlabel('')
xlim([0 xmax])

subplot(nplots,1,2)
rhohat(P,'cov',P.S.distance/1000);
% d = density(P, 'bandwidth', 5000);
% plotdz(S,d*1000,'dunit','km')
ylabel('LS density\newline [1/m]')
xlabel('')
xlim([0 xmax])
box on

subplot(nplots,1,3)
plotdz(S,STR.CHIRPSv2,'dunit','km','color','b')
ylabel('Acc. rainfall \newline [mm]')
xlabel('')
xlim([0 xmax])

subplot(nplots,1,4)
gmsu = crs(S,gms,'tau',0.9,'K',100,'mingradient',nan,'split',false);
hold on
gmsl = crs(S,gms,'tau',0.1,'K',100,'mingradient',nan,'split',false);
plotdzshaded(S,[gmsu gmsl],'dunit','km','facecolor',[0.7 .2 .1])
plotdz(S,gms,'color',[0.7 .2 .1],'dunit','km','LineWidth',0.5)
ylabel('Mean upsl.\newline gradient [°]')
xlabel('')
xlim([0 xmax])
box on

subplot(nplots,1,5)
hold on
clr = lines(numel(unique(geog)));
for r = 1:numel(unique(geog))
plotdzshaded(S,[getnal(S) +(geog == r)],'dunit','km','FaceColor',clr(r,:),...
    'FaceAlpha',1)
end
xlabel('')
ylabel('')
xlim([0 xmax])
colormap(gca,lines(numel(unique(geog))));
clim([0.5 numel(unique(geog))+0.5])
h = colorbar(gca,"westoutside");
h.Label.String = 'Lithozone';
h.Ticks = [1:5];
set(gca,'YTick',[])

subplot(nplots,1,6)
hold on
rw  = getnal(S,RW)+1;
clr = lines(numel(unique(rw)));
for r = 1:numel(unique(rw))
plotdzshaded(S,[getnal(S) +(rw == r)],'dunit','km','FaceColor',clr(r,:),...
    'FaceAlpha',1)
end
xlabel('')
ylabel('')
xlim([0 xmax])
clim([0.5 2.5])
colormap(gca,clr)
h2 = colorbar(gca,"westoutside");
h2.Label.String = 'Road widening';
h2.Ticks = 1:2;
h2.TickLabels = {'no','yes'};
set(gca,'YTick',[])


subplot(nplots,1,7)
plotdzshaded(P.S,intci*1000,'dunit','km')
hold on
plotdz(S,int*1000,'dunit','km','linewidth',0.5)
hold off
ylim([0 5])
ylabel('Modelled \newline LS density \newline [1/km]')
xlabel('Distance along road [km]')
xlim([0 xmax])
box on

spl = subplotlabel(gcf,'a','location','nw','pre','(','post',')','fontsize',8);

exportgraphics(gcf,'images/Fig_5_ploteffects.png','resolution',300);

%% Evaluate model performance (1)

% Calculate ROC curve
figure
tiledlayout(1,3,"TileSpacing","compact")
nexttile
[~,~,AUC] = roc(P,int);
xlabel('False positive rate')
ylabel('True positive rate')
nexttile
K = Kfun(P,'int',int,'method','okabe','maxdist',5000);
set(gca,'Layer','top')

nexttile

hold on
rho.bandwidth = 15;
for r = 1:100
    d = density(simulate(P,'intensity',int),'bandwidth',rho.bandwidth*1000);
    plotdz(P.S,d*1000,'dunit','km','color',[.7 .7 .7]);
% rhohat(simulate(P,'intensity',int),'covariate',P.S.distance/1000,...
%     'facecolor',[0.4940 0.1840 0.5560],'indicators',false,...
%     'color',[0.4940 0.1840 0.5560]);
end
d = density(P,'bandwidth',rho.bandwidth*1000);
plotdz(P.S,d*1000,'dunit','km','color','k','LineWidth',2);
xlabel('Distance along road [km]')
ylabel('\rho [km^{-1}]')
xlim([0 max(P.S.distance/1000)])
box on
set(gca,'Layer','top')

spl2 = subplotlabel(gcf,'a','location','nw',...
    'pre','(','post',')','fontsize',12);

set(gcf,'Position',[0.2690    0.4802    1.0280    0.2816]*1e3)

exportgraphics(gcf,'images/Fig_07_evaluatemodel.pdf','ContentType','vector')
exportgraphics(gcf,'images/Fig_07_evaluatemodel.png','ContentType','image','resolution',300)

%% Evaluate model using crossvalidation (2)

% Derive frequentist model (all landslides)
mdl = fitloglinear(P,{STR.CHIRPSv2 gms geog rw},'categorical',[3 4]);
[ypred,stats] = cvloglinear(P,mdl,'repeat',10);

% lstype
% 0 - New road-blocking landslides
% 1 - Blockage can be observed in imagery preceding Sep 2022
% 2 - Landslide visible in imagery preceding Sep 2022 but not blockage

% lstypedescribe = {'New LS', 'Previous road-blocking LS', 'Reactivated LS'}';
% 
% r = 2;
% Pt = P;
% Pt.PP = Pt.PP(lstype == r);
% mdl = fitloglinear(Pt,{STR.CHIRPSv2 gms geog rw},'categorical',[3 4]);
% [ypred,stats] = cvloglinear(Pt,mdl,'repeat',10);

%% Landslide susceptibility model with many more topographic variables

% Total curvature
TC = curvature(filter(DEM,'mean',[3 3]),'meanc');

% Topographic roughness
R  = roughness(DEM,'tri');

% Landuse
LU = GRIDobj('LULC\E060N40_PROBAV_LC100.tif');
LU = reproject2utm(LU,DEM,'method','nearest');

LU.Z(LU.Z == 80 | LU.Z == 90) = nan;
LU = inpaintnans(LU,'nearest');

lu = getnal(P.S,LU);

lu(lu == 30) = 20;
lu(lu >= 111 & lu <= 116 ) = 111;
lu(lu >= 121 & lu <= 126 ) = 121;


% Lookup-table for landcover classes
luvals = [0, 111, 112, 113, 114, 115, 116, 121, 122, 123, 124, 125, 126, 20, 30, 40, 50, 60, 70, 80, 90, 100, 200];
luclass = {'unknown', 'ENF_closed', 'EBF_closed', 'DNF_closed', 'DBF_closed',...
     'mixed_closed', 'unknown_closed', 'ENF_open', 'EBF_open', 'DNF_open',...
     'DBF_open', 'mixed _open', 'unknown_open', 'shrubland', 'herbaceous_vegetation', ...
     'cropland', 'built-up', 'bare_sparse_vegetation', 'snow_ice',...
    'permanent_inland_water', 'herbaceous_wetland', 'moss_lichen', 'sea'};
luclassnew = {'unknown', 'Closed forest','', '', '',...
     '', '', 'Open forest', '', '',...
     '', '', '', 'Shrubland', '', ...
     'Cropland', 'Built-up', '', '',...
    '', '', '', ''};
LUT = table(luvals(:),luclass(:),luclassnew(:),'VariableNames',{'value','class','classnew'});
clear luvals luclass

I = ismember(LUT.value,lu);
LUT = LUT(I,:);

[~,lu] = ismember(lu,LUT.value);

% Faults
faults = shaperead('faults\Fault.shp');
faults = projectshape(faults,DEM);
D2F    = distance(DEM,faults);


%% Run
VARS = {STR.CHIRPSv2 gms geog rw lu TC R D2F};
MODELS = {'Intercept only', ...
          '+ CHIRPS v2', ...
          '+ Gradient', ...
          '+ Lithozones', ...
          '+ Road widened', ...
          '+ Landcover', ...
          '+ Total Curv.',...
          '+ Roughness',...
          '+ Distance to Fault'};
AIC  = [];
Radjust = [];
for r = 0:numel(VARS)
    
    if r == 0
        mdl = fitloglinear(P,getnal(P.S)+1,'Intercept',false);
    else
    if r == 3
        catvar = 3;
    elseif r == 4
        catvar = [3 4];
    elseif r >= 5
        catvar = [3 4 5];
    else
        catvar = [];
    end
    [mdl,int] = fitloglinear(P,VARS(1:r),'categorical',catvar);
    end
    Radjust(r+1) = mdl.Rsquared.Adjusted;
    AIC(r+1) = mdl.ModelCriterion.AIC;

end
figure
plot(0:numel(VARS),AIC,'o-');
ylabel('AIC')
yyaxis right
plot(0:numel(VARS),Radjust,'o-')
ylabel('Adjusted R^2')
set(gca,'XTick',0:numel(VARS))
set(gca,'XTickLabel',MODELS)

set(gcf,'Position',[488.0000  396.2000  499.4000  365.8000])
exportgraphics(gcf,'images/Fig_08_evaluatemodel2.pdf','ContentType','vector')
exportgraphics(gcf,'images/Fig_08_evaluatemodel2.png','ContentType','image','resolution',300)

%% Projections
% [mdl,int,intci,predstats] = bayesloglinear(P2,{STR.CHIRPSv2 gms geog},'catvars',3,'prior','lasso');
X1 = [max(getnal(P.S,STR.CHIRPSv2),max(getnal(P.S,STR.CHIRPSv2))) gms geog];
pred = br_predict(X1, mdl.beta, mdl.beta0, mdl.retval, ...
                    'CI',[5 95],...
                    'display',false);

% modelled intensities
d   = distance(P.S,'node_to_node');
d   = mean(d);
intp = pred.prob_1./d;
intcip = [pred.prob_1_CI5_./d pred.prob_1_CI95_./d];
plotdz(P.S,smooth(P.S,intp*1000,'K',1000),'dunit','km')
hold on
plotdz(P.S,smooth(P.S,int*1000,'K',1000),'dunit','km')

X2 = X1;
X2(:,1) = X2(:,1)*1.05;
pred = br_predict(X2, mdl.beta, mdl.beta0, mdl.retval, ...
                    'CI',[5 95],...
                    'display',false);

% modelled intensities
d   = distance(P.S,'node_to_node');
d   = mean(d);
intp = pred.prob_1./d;
intcip = [pred.prob_1_CI5_./d pred.prob_1_CI95_./d];
plotdz(P.S,smooth(P.S,intp*1000,'K',1000),'dunit','km')
hold off
